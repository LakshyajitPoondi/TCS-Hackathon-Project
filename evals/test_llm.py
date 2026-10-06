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

class _ChatResponse:
    """Minimal OpenAI-compatible reply; status 429 carries an optional Retry-After header."""
    def __init__(self,status=200,headers=None): self.status_code=status; self.headers=headers or {}
    def raise_for_status(self):
        if self.status_code>=400: raise httpx.HTTPStatusError('status',request=httpx.Request('POST','https://x'),response=httpx.Response(self.status_code))
    def json(self): return {'choices':[{'message':{'content':json.dumps(VALID)}}],'usage':{'total_tokens':9}}

def _capture(monkeypatch,replies):
    sent=[]
    def post(url,**kw): sent.append((url,kw)); return replies.pop(0)
    monkeypatch.setattr(httpx,'post',post); return sent

@pytest.mark.parametrize('base',['https://generativelanguage.googleapis.com/v1beta/openai/','https://generativelanguage.googleapis.com/v1beta/openai'])
def test_gemini_url_auth_and_json_body(base,monkeypatch,tmp_path):
    monkeypatch.setattr(config,'LLM_PROVIDER','openai_compatible'); monkeypatch.setattr(config,'LLM_BASE_URL',base)
    monkeypatch.setattr(config,'LLM_API_KEY','test-process-value'); monkeypatch.setattr(config,'LLM_CACHE_DIR',tmp_path)
    sent=_capture(monkeypatch,[_ChatResponse()])
    assert llm.generate('x',PAYLOAD)[1]=='llm'
    url,kw=sent[0]
    assert url=='https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
    assert kw['headers']['Authorization']=='Bearer test-process-value'
    assert kw['json']['response_format']=={'type':'json_object'}

def test_gemini_alias_uses_default_base_url(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'LLM_PROVIDER','gemini'); monkeypatch.setattr(config,'LLM_BASE_URL','')
    monkeypatch.setattr(config,'LLM_API_KEY','test-process-value'); monkeypatch.setattr(config,'LLM_CACHE_DIR',tmp_path)
    sent=_capture(monkeypatch,[_ChatResponse()]); llm.reset_calls()
    assert llm.generate('x',PAYLOAD)[1]=='llm'
    assert sent[0][0]=='https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
    assert llm.calls()[-1]['provider']=='gemini'

def test_groq_default_url_unchanged(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'LLM_PROVIDER','groq'); monkeypatch.setattr(config,'LLM_BASE_URL','')
    monkeypatch.setattr(config,'LLM_API_KEY','test-process-value'); monkeypatch.setattr(config,'LLM_CACHE_DIR',tmp_path)
    sent=_capture(monkeypatch,[_ChatResponse()])
    assert llm.generate('x',PAYLOAD)[1]=='llm'
    assert sent[0][0]=='https://api.groq.com/openai/v1/chat/completions'

def test_rate_limit_backoff_then_success(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'LLM_PROVIDER','gemini'); monkeypatch.setattr(config,'LLM_BASE_URL','')
    monkeypatch.setattr(config,'LLM_API_KEY','test-process-value'); monkeypatch.setattr(config,'LLM_CACHE_DIR',tmp_path)
    delays=[]; monkeypatch.setattr(llm,'_sleep',delays.append)
    sent=_capture(monkeypatch,[_ChatResponse(429),_ChatResponse(429,{'retry-after':'3'}),_ChatResponse(429,{'retry-after':'999'}),_ChatResponse()])
    assert llm.generate('x',PAYLOAD)[1]=='llm'
    assert len(sent)==4 and delays==[1.0,3.0,llm.RATE_LIMIT_MAX_DELAY]

def test_rate_limit_exhausted_falls_back_to_template(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'LLM_PROVIDER','gemini'); monkeypatch.setattr(config,'LLM_BASE_URL','')
    monkeypatch.setattr(config,'LLM_API_KEY','test-process-value'); monkeypatch.setattr(config,'LLM_CACHE_DIR',tmp_path)
    monkeypatch.setattr(llm,'_sleep',lambda s:None)
    attempts=(llm.RATE_LIMIT_RETRIES+1)*(config.LLM_MAX_RETRIES+1)
    sent=_capture(monkeypatch,[_ChatResponse(429) for _ in range(attempts)]); llm.reset_calls()
    assert llm.generate('x',PAYLOAD)==(None,'template')
    assert len(sent)==attempts and llm.calls()[-1]['fallback_reason']=='HTTPStatusError'
