"""Hard-scoped hybrid retrieval: machine-scope filter in SQL first, then lexical + vector ranking, RRF fusion.

Postgres: lexical = full-text search (ts_rank over a generated tsvector, GIN index); vector = pgvector
`embedding <=> query` (HNSW, cosine) with ORDER BY ... LIMIT in SQL. Only candidate chunks are loaded.
SQLite (tests/dev only): BM25 and numpy cosine over the in-scope chunks.
"""
import logging
import re
import httpx
import numpy as np
from rank_bm25 import BM25Plus
from sqlalchemy import select, text as sql_text, bindparam, Float
from backend import db
from backend.core import config
from engine.rag import _tokens, build_query

log=logging.getLogger('rca.retrieval')
PRIORITY={'machine':0,'model':1,'line':2,'plant':3}
RRF_K=60
_model=None

def embedding_key():
    return config.EMBEDDINGS_PROVIDER+':'+config.EMBEDDINGS_MODEL

def embed(texts):
    global _model
    if config.EMBEDDINGS_PROVIDER=='fastembed':
        from fastembed import TextEmbedding
        if _model is None: _model=TextEmbedding(model_name=config.EMBEDDINGS_MODEL,cache_dir=str(config.DATA_DIR/'embedding_cache'))
        return [list(map(float,v)) for v in _model.embed(texts)]
    if config.EMBEDDINGS_PROVIDER=='openai_compatible':
        if not config.EMBEDDINGS_API_KEY or not config.EMBEDDINGS_BASE_URL: raise ValueError('embedding key/base URL missing')
        response=httpx.post(config.EMBEDDINGS_BASE_URL.rstrip('/')+'/embeddings',headers={'Authorization':'Bearer '+config.EMBEDDINGS_API_KEY},
                            json={'model':config.EMBEDDINGS_MODEL,'input':texts},timeout=config.LLM_TIMEOUT_SECONDS)
        response.raise_for_status()
        return [row['embedding'] for row in sorted(response.json()['data'],key=lambda row:row['index'])]
    raise ValueError('embeddings disabled')

def embed_query(query):
    vector=embed([query])[0]
    _check_vector(vector)
    return vector

def _check_vector(vector):
    if len(vector)!=db.EMBEDDING_DIM or not np.isfinite(np.asarray(vector,dtype=float)).all():
        raise ValueError(f'embedding must be {db.EMBEDDING_DIM} finite values')

def embed_chunks(chunks,batch_size=64):
    """Store embeddings on chunk objects (caller commits). Returns (embedded, status). Never raises."""
    if config.EMBEDDINGS_PROVIDER=='none' or not chunks:
        return 0,'disabled'
    key=embedding_key();done=0
    try:
        for start in range(0,len(chunks),batch_size):
            batch=chunks[start:start+batch_size]
            vectors=embed([c.text for c in batch])
            if len(vectors)!=len(batch):raise ValueError('embedding count mismatch')
            for c,v in zip(batch,vectors):
                _check_vector(v);c.embedding=list(map(float,v));c.embedding_model=key;done+=1
        return done,'enabled'
    except Exception as exc:
        log.warning('chunk embedding skipped: %s',type(exc).__name__)
        return done,'fallback:'+type(exc).__name__

def cosine(query,vectors):
    q=np.asarray(query,dtype=float); matrix=np.asarray(vectors,dtype=float)
    if not np.isfinite(q).all() or not np.isfinite(matrix).all() or matrix.ndim!=2 or matrix.shape[1]!=len(q): raise ValueError('invalid embedding vectors')
    return matrix@q / np.maximum(np.linalg.norm(matrix,axis=1)*np.linalg.norm(q),1e-12)

def _scoped_doc_ids(uids):
    """SQL subquery: active documents linked to any requested physical machine (links follow scope rules)."""
    return (select(db.DocumentMachineLink.doc_id).join(db.Document,db.Document.doc_id==db.DocumentMachineLink.doc_id)
            .where(db.DocumentMachineLink.machine_uid.in_(uids),db.Document.status=='active').distinct())

def _ts_query(query):
    # Tokens are [a-z]+ only, so they cannot inject tsquery syntax. OR semantics like BM25.
    tokens=sorted(set(_tokens(query)))
    return ' | '.join(tokens)

def _lexical_postgres(session,uids,query,pool):
    expr=_ts_query(query)
    if not expr:return {}
    rows=session.execute(sql_text(
        "SELECT c.chunk_id, ts_rank(c.tsv, q) AS score FROM document_chunks c, to_tsquery('english', :q) q "
        "WHERE c.doc_id IN (SELECT l.doc_id FROM document_machine_links l JOIN documents d ON d.doc_id = l.doc_id "
        "WHERE l.machine_uid IN :uids AND d.status = 'active') AND c.tsv @@ q "
        "ORDER BY score DESC, c.chunk_id LIMIT :pool").bindparams(bindparam('uids',expanding=True)),
        {'q':expr,'uids':list(uids),'pool':pool}).all()
    return {r.chunk_id:float(r.score) for r in rows}

def _vector_postgres(session,uids,vector,pool):
    # Iterative HNSW scans keep filtered queries from returning fewer than LIMIT rows (pgvector >= 0.8).
    session.execute(sql_text("SET LOCAL hnsw.iterative_scan = strict_order"))
    distance=db.DocumentChunk.embedding.op('<=>',return_type=Float())(vector)
    rows=session.execute(select(db.DocumentChunk.chunk_id,distance.label('distance'))
        .where(db.DocumentChunk.doc_id.in_(_scoped_doc_ids(uids)),db.DocumentChunk.embedding.is_not(None),
               db.DocumentChunk.embedding_model==embedding_key())
        .order_by(distance,db.DocumentChunk.chunk_id).limit(pool)).all()
    return {r.chunk_id:1.0-float(r.distance) for r in rows}

def _scoped_chunks_sqlite(session,uids):
    return list(session.scalars(select(db.DocumentChunk).where(db.DocumentChunk.doc_id.in_(_scoped_doc_ids(uids))).order_by(db.DocumentChunk.chunk_id)))

def _lexical_sqlite(chunks,titles,query):
    if not chunks:return {}
    tokenized=[_tokens(c.text+' '+titles[c.doc_id]) or ['empty'] for c in chunks]
    scores=BM25Plus(tokenized,delta=0).get_scores(_tokens(query))
    return {c.chunk_id:float(s) for c,s in zip(chunks,scores) if s>0}

def _vector_sqlite(chunks,vector):
    usable=[c for c in chunks if c.embedding is not None and c.embedding_model==embedding_key()]
    if not usable:return {}
    sims=cosine(vector,[c.embedding for c in usable])
    return {c.chunk_id:float(s) for c,s in zip(usable,sims)}

def search(machine_uids,query,top_k=None):
    """Filtering happens in SQL before ranking; external callers cannot bypass machine identity."""
    if isinstance(machine_uids,str):machine_uids=[machine_uids]
    k=top_k or config.RAG_TOP_K;pool=max(50,k*10)
    with db.Session() as session:
        machines=[session.get(db.Machine,uid) for uid in machine_uids]
        if not machines or any(m is None for m in machines): raise ValueError('Unknown physical machine')
        uids=[m.machine_uid for m in machines]
        links=session.execute(select(db.DocumentMachineLink.doc_id,db.DocumentMachineLink.machine_uid)
                              .where(db.DocumentMachineLink.machine_uid.in_(uids))).all()
        matched={}
        for doc_id,uid in links:matched.setdefault(doc_id,[]).append(uid)
        docs={d.doc_id:d for d in session.scalars(select(db.Document).order_by(db.Document.doc_id))}
        allowed={did:d for did,d in docs.items() if d.status=='active' and did in matched}
        filtered=[{'doc_id':d.doc_id,'title':d.title,'reason':'Document is '+d.status if d.status!='active' else 'Scope does not include relevant physical machines'}
                  for did,d in docs.items() if did not in allowed]
        if not allowed:return {'hits':[],'filtered':filtered,'embedding_status':'not_used'}
        postgres=db.is_postgres(session.get_bind())
        chunks=None if postgres else _scoped_chunks_sqlite(session,uids)
        titles={did:d.title for did,d in allowed.items()}
        lexical=_lexical_postgres(session,uids,query,pool) if postgres else _lexical_sqlite(chunks,titles,query)
        semantic=None;status='disabled'
        if config.EMBEDDINGS_PROVIDER!='none':
            try:
                vector=embed_query(query)
                semantic=_vector_postgres(session,uids,vector,pool) if postgres else _vector_sqlite(chunks,vector)
                status='enabled'
            except Exception as exc:
                session.rollback();semantic=None
                status='fallback:'+type(exc).__name__;log.warning('embeddings fallback: %s',type(exc).__name__)
        candidates=set(lexical)|set(semantic or {})
        if not candidates:return {'hits':[],'filtered':filtered,'embedding_status':status}
        rows={c.chunk_id:c for c in session.scalars(select(db.DocumentChunk).where(db.DocumentChunk.chunk_id.in_(candidates)))}
        scope_rank=lambda cid:PRIORITY[allowed[rows[cid].doc_id].scope]
        lex_order=sorted(lexical,key=lambda cid:(-round(lexical[cid],12),scope_rank(cid),cid))
        if semantic:
            sem_order=sorted(semantic,key=lambda cid:(-round(semantic[cid],12),scope_rank(cid),cid))
            score={cid:0.0 for cid in candidates}
            for rank,cid in enumerate(lex_order,1):score[cid]+=1/(RRF_K+rank)
            for rank,cid in enumerate(sem_order,1):score[cid]+=1/(RRF_K+rank)
        else:
            score=dict(lexical)
        order=sorted(candidates,key=lambda cid:(-round(score[cid],12),scope_rank(cid),cid))
        hits=[]
        for cid in order:
            relevance=max(lexical.get(cid,0.0),(semantic or {}).get(cid,0.0))
            if relevance<=config.RAG_MIN_SCORE:continue
            c=rows[cid];doc=allowed[c.doc_id];m=sorted(matched[c.doc_id])
            hits.append({'doc_id':doc.doc_id,'title':doc.title,'version':doc.version,'doc_type':doc.doc_type,'scope':doc.scope,
                         'matched_machine':m,'why_allowed':f'{doc.scope} scope includes '+', '.join(m),
                         'chunk_id':c.chunk_id,'page_or_section':c.page_or_section,'score':round(score[cid],6),
                         'snippet':c.text[:700],'text':c.text})
            if len(hits)>=k:break
        return {'hits':hits,'filtered':filtered,'embedding_status':status}

def for_hypothesis(h,line,machines):
    target=h.get('target')
    uids=[line+'/'+target] if target in machines else [line+'/'+m for m in machines]
    return search(uids,build_query(h))

STEP_RE=re.compile(r'(?:^|\s)\d+\.\s+(.+?)(?=\s\d+\.\s|$)')

def verification_steps(hits):
    """Numbered steps from retrieved chunks, best-ranked chunks first. B4: keep only the step sentence,
    never trailing prose. A raw "Review reference" is used only when no retrieved chunk has numbered steps."""
    steps=[]
    for hit in hits:
        matches=[m for m in (_first_sentence(x) for x in STEP_RE.findall(hit['text'])) if m]
        for text in matches[:2]:
            steps.append({'step':text,'source':hit['doc_id'],'chunk_id':hit['chunk_id']})
        if len(steps)>=3:break
    if not steps and hits:
        steps.append({'step':'Review reference: '+hits[0]['text'][:400],'source':hits[0]['doc_id'],'chunk_id':hits[0]['chunk_id']})
    return steps[:3]

def draft_line(step):
    """How a step appears inside an RCA draft. Raw reference text is cited, not quoted, so the draft never
    repeats document prose as if it were an observed claim."""
    if step['step'].startswith('Review reference:'):
        return f"- Review reference {step['source']} ({step.get('chunk_id') or ''})"
    return f"- {step['step']} ({step['source']}, {step.get('chunk_id') or ''})"

def _first_sentence(text):
    """Keep only the step itself: stop at the first sentence end or a markdown heading marker."""
    text=re.split(r'\s#{1,6}\s',text,maxsplit=1)[0]
    match=re.match(r'(.+?[.!?])(?:\s|$)',text)
    return (match.group(1) if match else text).strip()

def provenance(results):
    accessed={};filtered={}
    for rank,result in results.items():
        for hit in result['hits']:
            did=hit['doc_id']
            if did not in accessed:
                accessed[did]={k:hit[k] for k in ('doc_id','title','version','doc_type','scope','matched_machine','why_allowed')}
                accessed[did].update(chunks=[],used_for=[])
            a=accessed[did]
            if hit['chunk_id'] not in [c['chunk_id'] for c in a['chunks']]:a['chunks'].append({k:hit[k] for k in ('chunk_id','page_or_section','score','snippet')})
            a['used_for'].append(f'hypothesis {rank}')
        for row in result['filtered']:filtered[row['doc_id']]=row
    return list(accessed.values()),[row for did,row in filtered.items() if did not in accessed]
