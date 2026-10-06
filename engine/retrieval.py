"""Hard scoped retrieval over active SQLite chunks, BM25 plus optional RRF."""
import logging
import re
import httpx
import numpy as np
from rank_bm25 import BM25Plus
from sqlalchemy import select
from backend import db
from backend.core import config
from backend.services.documents import machine_allowed
from engine.rag import _tokens, build_query

log=logging.getLogger('rca.retrieval')
PRIORITY={'machine':0,'model':1,'line':2,'plant':3}
_model=None

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

def cosine(query,vectors):
    q=np.asarray(query,dtype=float); matrix=np.asarray(vectors,dtype=float)
    if not np.isfinite(q).all() or not np.isfinite(matrix).all() or matrix.ndim!=2 or matrix.shape[1]!=len(q): raise ValueError('invalid embedding vectors')
    return matrix@q / np.maximum(np.linalg.norm(matrix,axis=1)*np.linalg.norm(q),1e-12)

def search(machine_uids,query,top_k=None):
    """Filtering happens before indexing; external callers cannot bypass identity."""
    if isinstance(machine_uids,str):machine_uids=[machine_uids]
    with db.Session.begin() as session:
        machines=[session.get(db.Machine,uid) for uid in machine_uids]
        if not machines or any(m is None for m in machines): raise ValueError('Unknown physical machine')
        docs=list(session.scalars(select(db.Document).order_by(db.Document.doc_id)))
        allowed={};filtered=[]
        for doc in docs:
            matched=[m.machine_uid for m in machines if machine_allowed(m,doc.scope,doc.targets)]
            if doc.status!='active':reason='Document is '+doc.status
            elif not matched:reason='Scope does not include relevant physical machines'
            else: allowed[doc.doc_id]=(doc,matched);continue
            filtered.append({'doc_id':doc.doc_id,'title':doc.title,'reason':reason})
        chunks=list(session.scalars(select(db.DocumentChunk).where(db.DocumentChunk.doc_id.in_(allowed)).order_by(db.DocumentChunk.chunk_id))) if allowed else []
        if not chunks:return {'hits':[],'filtered':filtered,'embedding_status':'not_used'}
        tokenized=[_tokens(c.text+' '+allowed[c.doc_id][0].title) or ['empty'] for c in chunks]
        bm=BM25Plus(tokenized,delta=0).get_scores(_tokens(query))
        lex=sorted(range(len(chunks)),key=lambda i:(-float(bm[i]),PRIORITY[allowed[chunks[i].doc_id][0].scope],chunks[i].chunk_id))
        fusion={i:1/(60+rank) for rank,i in enumerate(lex,1)}
        semantic=None;status='disabled'
        if config.EMBEDDINGS_PROVIDER!='none':
            try:
                key=config.EMBEDDINGS_PROVIDER+':'+config.EMBEDDINGS_MODEL
                missing=[c for c in chunks if c.embedding is None or c.embedding_model!=key]
                vectors=embed([query]+[c.text for c in missing])
                if len(vectors)!=len(missing)+1:raise ValueError('embedding count mismatch')
                for c,v in zip(missing,vectors[1:]):c.embedding=v;c.embedding_model=key
                semantic=cosine(vectors[0],[c.embedding for c in chunks])
                for rank,i in enumerate(sorted(range(len(chunks)),key=lambda i:-semantic[i]),1):fusion[i]+=1/(60+rank)
                status='enabled'
            except Exception as exc:
                status='fallback:'+type(exc).__name__;log.warning('embeddings fallback: %s',type(exc).__name__)
        order=sorted(range(len(chunks)),key=lambda i:(-round(fusion[i] if semantic is not None else float(bm[i]),12),PRIORITY[allowed[chunks[i].doc_id][0].scope],chunks[i].chunk_id))
        hits=[]
        for i in order:
            relevance=max(float(bm[i]),float(semantic[i]) if semantic is not None else 0)
            if relevance<=config.RAG_MIN_SCORE:continue
            c=chunks[i];doc,matched=allowed[c.doc_id]
            hits.append({'doc_id':doc.doc_id,'title':doc.title,'version':doc.version,'doc_type':doc.doc_type,'scope':doc.scope,
                         'matched_machine':matched,'why_allowed':f'{doc.scope} scope includes '+', '.join(matched),
                         'chunk_id':c.chunk_id,'page_or_section':c.page_or_section,'score':round(fusion[i] if semantic is not None else float(bm[i]),6),
                         'snippet':c.text[:700],'text':c.text})
            if len(hits)>=(top_k or config.RAG_TOP_K):break
        return {'hits':hits,'filtered':filtered,'embedding_status':status}

def for_hypothesis(h,line,machines):
    target=h.get('target')
    uids=[line+'/'+target] if target in machines else [line+'/'+m for m in machines]
    return search(uids,build_query(h))

def verification_steps(hits):
    steps=[]
    for hit in hits:
        matches=re.findall(r'(?:^|\s)\d+\.\s+(.+?)(?=\s\d+\.\s|$)',hit['text'])
        chosen=matches[:2] or ['Review reference: '+hit['text'][:400]]
        for text in chosen:
            steps.append({'step':text,'source':hit['doc_id'],'chunk_id':hit['chunk_id']})
        if len(steps)>=3:break
    return steps[:3]

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
