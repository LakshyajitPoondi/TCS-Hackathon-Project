from backend import db
from backend.core import config
from backend.services.documents import ingest
from engine import retrieval

def test_hard_scope_active_and_citations(client,monkeypatch):
    with db.Session.begin() as s:
        for uid in ('LINE-A/IMM-01','LINE-B/IMM-01'):
            ingest(s,'manual.md',f'# Manual\n{uid} cooling temperature vibration inspect coolant flow.'.encode(),uid,'manual','1','machine',[uid],'admin',doc_id=uid.replace('/','-'))
        pending=ingest(s,'ambiguous.txt',b'IMM-01 cooling temperature vibration','pending','manual','1','machine',['LINE-A/IMM-01'],'admin')
    result=retrieval.search('LINE-A/IMM-01','cooling temperature vibration coolant flow',20)
    ids={h['doc_id'] for h in result['hits']}
    assert 'LINE-A-IMM-01' in ids and 'LINE-B-IMM-01' not in ids and pending.doc_id not in ids
    assert any(f['doc_id']=='LINE-B-IMM-01' for f in result['filtered'])
    monkeypatch.setattr(config,'EMBEDDINGS_PROVIDER','openai_compatible')
    monkeypatch.setattr(retrieval,'embed',lambda texts:[[1.,len(t)%7+1.] for t in texts])
    result=retrieval.search('LINE-A/IMM-01','cooling temperature vibration',20)
    assert result['embedding_status']=='enabled' and all(h['doc_id']!='LINE-B-IMM-01' for h in result['hits'])
    with db.Session() as s:assert s.get(db.DocumentChunk,result['hits'][0]['chunk_id']).embedding
    response=client.post('/api/incidents/INC-001/analyze');assert response.status_code==200,response.text
    data=response.json();assert data['documents_accessed']
    retrieved={c['chunk_id'] for d in data['documents_accessed'] for c in d['chunks']}
    assert all(step['chunk_id'] in retrieved for h in data['hypotheses'] for step in h['verification_steps'])

def test_embedding_failure_lexical_and_scope_tie(monkeypatch):
    with db.Session.begin() as s:
        for scope,targets,did in [('plant',[],'tie-plant'),('line',['LINE-A'],'tie-line'),('model',['IMM'],'tie-model'),('machine',['LINE-A/IMM-01'],'tie-machine')]:
            ingest(s,'guide.md',b'# Guide\nunique cooling coolant inspect.',did,'manual','1',scope,targets,'admin',doc_id=did)
    result=retrieval.search('LINE-A/IMM-01','unique coolant',20)
    assert [h['doc_id'] for h in result['hits'] if h['doc_id'].startswith('tie-')]==['tie-machine','tie-model','tie-line','tie-plant']
    monkeypatch.setattr(config,'EMBEDDINGS_PROVIDER','openai_compatible');monkeypatch.setattr(config,'EMBEDDINGS_API_KEY','')
    assert retrieval.search('LINE-A/IMM-01','unique coolant')['embedding_status'].startswith('fallback')
