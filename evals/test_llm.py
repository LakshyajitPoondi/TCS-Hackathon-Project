import json
import httpx
import pytest
from engine import llm
from backend.core import config
from backend import db

PAYLOAD={'hypotheses':[{'rank':1}], 'template_draft':'Verification required.'}
VALID={'hypotheses':[{'rank':1,'narrative':'Hypothesis requires verification.','verification_steps':[]}], 'rca_draft':'Verification required.'}

def test_no_key_fake_cache_and_rank(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'LLM_CACHE_DIR',tmp_path)
    monkeypatch.setattr(config,'LLM_API_KEY','')
    monkeypatch.setattr(config,'LLM_PROVIDER','groq')
    llm.reset_calls(); assert llm.generate('x',PAYLOAD)==(None,'template')
    assert llm.calls()[-1]['fallback_reason']=='no_key'
    monkeypatch.setattr(config,'LLM_PROVIDER','fake')
    out,source=llm.generate('x',PAYLOAD); assert source=='llm' and out
    llm.save_cache('x',PAYLOAD,VALID); assert llm.load_cache('x',PAYLOAD)
    llm._cache_path('x',PAYLOAD).write_text('{bad')
    assert llm.load_cache('x',PAYLOAD) is None
    llm.save_cache('x',PAYLOAD,{**VALID,'hypotheses':[]}); assert llm.load_cache('x',PAYLOAD) is None
    original=llm.input_hash(PAYLOAD); monkeypatch.setattr(config,'LLM_MODEL','different'); assert original!=llm.input_hash(PAYLOAD)

@pytest.mark.parametrize('provider',['groq','openai_compatible','anthropic'])
def test_http_provider_and_failures(provider,monkeypatch,tmp_path):
    monkeypatch.setattr(config,'LLM_PROVIDER',provider); monkeypatch.setattr(config,'LLM_API_KEY','test-process-value')
    monkeypatch.setattr(config,'LLM_BASE_URL','https://example.invalid/v1'); monkeypatch.setattr(config,'LLM_CACHE_DIR',tmp_path)
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'choices':[{'message':{'content':json.dumps(VALID)}}], 'content':[{'type':'text','text':json.dumps(VALID)}], 'usage':{'total_tokens':12}}
    monkeypatch.setattr(httpx,'post',lambda *a,**kw: Response())
    assert llm.generate('x',PAYLOAD)[1]=='llm'
    def timeout(*a,**kw): raise httpx.ReadTimeout('test')
    monkeypatch.setattr(httpx,'post',timeout); llm.reset_calls()
    assert llm.generate('x',PAYLOAD)[1]=='template' and len(llm.calls())==config.LLM_MAX_RETRIES+1
    monkeypatch.setattr(httpx,'post',lambda *a,**kw: type('Bad',(),{'raise_for_status':lambda self:None,'json':lambda self:{}})())
    assert llm.generate('x',PAYLOAD)[1]=='template'

def test_analysis_persisted(client,monkeypatch):
    monkeypatch.setattr(config,'LLM_API_KEY',''); monkeypatch.setattr(config,'LLM_PROVIDER','groq')
    response=client.post('/api/incidents/INC-001/analyze'); assert response.status_code==200,response.text
    assert response.json()['text_source']=='template'
    with db.Session() as session:
        run=session.get(db.AnalysisRun,response.json()['run_id']); assert run.llm_calls[-1]['fallback_reason']=='no_key'
