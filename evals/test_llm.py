import json
import httpx
import pytest
from sqlalchemy import select, func
from engine import llm
from backend.core import config
from backend import db

PAYLOAD={'hypotheses':[{'rank':1}], 'template_draft':'Verification required.'}
VALID={'hypotheses':[{'rank':1,'narrative':'Hypothesis requires verification.','verification_steps':[]}], 'rca_draft':'Verification required.'}

def usage_rows():
    with db.Session() as s:return list(s.scalars(select(db.LLMUsage).order_by(db.LLMUsage.id)))

def test_no_key_fake_cache_and_rank(monkeypatch):
    monkeypatch.setattr(config,'LLM_API_KEY','')
    monkeypatch.setattr(config,'LLM_PROVIDER','groq')
    llm.reset_calls(); assert llm.generate('x',PAYLOAD)==(None,'template')
    assert llm.calls()[-1]['fallback_reason']=='no_key' and usage_rows()==[]
    monkeypatch.setattr(config,'LLM_PROVIDER','fake')
    out,source=llm.generate('x',PAYLOAD); assert source=='llm' and out
    llm.save_cache('x',PAYLOAD,VALID); assert llm.load_cache('x',PAYLOAD)
    with db.Session.begin() as s:s.get(db.LLMCache,llm.cache_key('wording','x',PAYLOAD)).output={'bad':True}
    assert llm.load_cache('x',PAYLOAD) is None
    llm.save_cache('x',PAYLOAD,{**VALID,'hypotheses':[]}); assert llm.load_cache('x',PAYLOAD) is None
    original=llm.input_hash(PAYLOAD); monkeypatch.setattr(config,'LLM_MODEL','different'); assert original!=llm.input_hash(PAYLOAD)

def test_cache_hit_makes_no_request(monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','fake')
    llm.save_cache('INC-X',PAYLOAD,VALID)
    llm.reset_calls(); assert llm.generate('INC-X',PAYLOAD)[1]=='llm'
    assert llm.calls()[-1].get('cache_hit') and usage_rows()==[]

@pytest.mark.parametrize('provider',['groq','openai_compatible','anthropic'])
def test_http_provider_and_failures(provider,monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER',provider); monkeypatch.setattr(config,'LLM_API_KEY','test-process-value')
    monkeypatch.setattr(config,'LLM_BASE_URL','https://example.invalid/v1')
    class Response:
        status_code=200;headers={}
        def raise_for_status(self): pass
        def json(self): return {'choices':[{'message':{'content':json.dumps(VALID)}}], 'content':[{'type':'text','text':json.dumps(VALID)}], 'usage':{'total_tokens':12}}
    monkeypatch.setattr(httpx,'post',lambda *a,**kw: Response())
    assert llm.generate('x',PAYLOAD)[1]=='llm'
    def timeout(*a,**kw): raise httpx.ReadTimeout('test')
    monkeypatch.setattr(httpx,'post',timeout); llm.reset_calls()
    assert llm.generate('y',PAYLOAD)[1]=='template' and len(llm.calls())==config.LLM_MAX_RETRIES+1
    monkeypatch.setattr(httpx,'post',lambda *a,**kw: type('Bad',(),{'status_code':200,'headers':{},'raise_for_status':lambda self:None,'json':lambda self:{}})())
    assert llm.generate('z',PAYLOAD)[1]=='template'

def test_analysis_persisted(client,monkeypatch):
    monkeypatch.setattr(config,'LLM_API_KEY',''); monkeypatch.setattr(config,'LLM_PROVIDER','groq')
    response=client.post('/api/incidents/INC-001/analyze'); assert response.status_code==200,response.text
    assert response.json()['text_source']=='template' and response.json()['llm_usage']['requests']==0
    with db.Session() as session:
        run=session.get(db.AnalysisRun,response.json()['run_id']); assert run.llm_calls[-1]['fallback_reason']=='no_key'

class _ChatResponse:
    """Minimal OpenAI-compatible reply; error statuses carry optional headers and body text."""
    def __init__(self,status=200,headers=None,text=''): self.status_code=status; self.headers=headers or {}; self.text=text
    def raise_for_status(self):
        if self.status_code>=400: raise httpx.HTTPStatusError('status',request=httpx.Request('POST','https://x'),response=httpx.Response(self.status_code))
    def json(self): return {'choices':[{'message':{'content':json.dumps(VALID)}}],'usage':{'total_tokens':9}}

def _capture(monkeypatch,replies):
    sent=[]
    def post(url,**kw): sent.append((url,kw)); return replies.pop(0)
    monkeypatch.setattr(httpx,'post',post); return sent

@pytest.mark.parametrize('base',['https://generativelanguage.googleapis.com/v1beta/openai/','https://generativelanguage.googleapis.com/v1beta/openai'])
def test_gemini_url_auth_and_json_body(base,monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','openai_compatible'); monkeypatch.setattr(config,'LLM_BASE_URL',base)
    monkeypatch.setattr(config,'LLM_API_KEY','test-process-value')
    sent=_capture(monkeypatch,[_ChatResponse()])
    assert llm.generate('x',PAYLOAD)[1]=='llm'
    url,kw=sent[0]
    assert url=='https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
    assert kw['headers']['Authorization']=='Bearer test-process-value'
    assert kw['json']['response_format']=={'type':'json_object'}

def test_gemini_alias_uses_default_base_url(monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','gemini'); monkeypatch.setattr(config,'LLM_BASE_URL','')
    monkeypatch.setattr(config,'LLM_API_KEY','test-process-value')
    sent=_capture(monkeypatch,[_ChatResponse()]); llm.reset_calls()
    assert llm.generate('x',PAYLOAD)[1]=='llm'
    assert sent[0][0]=='https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
    assert llm.calls()[-1]['provider']=='gemini'

def test_groq_default_url_unchanged(monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','groq'); monkeypatch.setattr(config,'LLM_BASE_URL','')
    monkeypatch.setattr(config,'LLM_API_KEY','test-process-value')
    sent=_capture(monkeypatch,[_ChatResponse()])
    assert llm.generate('x',PAYLOAD)[1]=='llm'
    assert sent[0][0]=='https://api.groq.com/openai/v1/chat/completions'

QUOTA_BODY='{"error":{"code":429,"status":"RESOURCE_EXHAUSTED","message":"Quota exceeded for metric: generate_content_free_tier_requests, limit: 20. Please retry in 22h36m"}}'

def test_b2_quota_is_never_retried_and_blocks_later_calls(monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','gemini'); monkeypatch.setattr(config,'LLM_BASE_URL','')
    monkeypatch.setattr(config,'LLM_API_KEY','test-process-value'); monkeypatch.setattr(config,'LLM_MAX_RETRIES',3)
    sleeps=[];monkeypatch.setattr(llm,'_sleep',sleeps.append)
    sent=_capture(monkeypatch,[_ChatResponse(429,text=QUOTA_BODY)]); llm.reset_calls()
    assert llm.generate('x',PAYLOAD)==(None,'template')
    assert len(sent)==1 and sleeps==[] and llm.calls()[-1]['fallback_reason']=='quota_exhausted'
    rows=usage_rows();assert rows[-1].status=='quota_exhausted' and rows[-1].blocked_until is not None
    # Retry time ~22h36m is respected: the next call does not reach the provider at all.
    assert llm.generate('y',PAYLOAD)==(None,'template') and len(sent)==1
    assert llm.calls()[-1]['fallback_reason']=='quota_exhausted' and llm.status()['blocked_until']

def test_b2_long_retry_after_is_quota_and_short_429_not_retried(monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','gemini'); monkeypatch.setattr(config,'LLM_API_KEY','test-process-value')
    monkeypatch.setattr(llm,'_sleep',lambda s:None)
    sent=_capture(monkeypatch,[_ChatResponse(429,{'retry-after':'5'})])
    assert llm.generate('x',PAYLOAD)==(None,'template') and len(sent)==1 and llm.calls()[-1]['fallback_reason']=='rate_limited'
    sent=_capture(monkeypatch,[_ChatResponse(429,{'retry-after':'7200'})])
    assert llm.generate('y',PAYLOAD)==(None,'template') and len(sent)==1 and usage_rows()[-1].status=='quota_exhausted'

def test_b2_503_retried_at_most_twice(monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','gemini'); monkeypatch.setattr(config,'LLM_API_KEY','test-process-value')
    monkeypatch.setattr(config,'LLM_MAX_RETRIES',0)
    delays=[];monkeypatch.setattr(llm,'_sleep',delays.append)
    sent=_capture(monkeypatch,[_ChatResponse(503),_ChatResponse(503),_ChatResponse()])
    assert llm.generate('x',PAYLOAD)[1]=='llm' and len(sent)==3 and delays==[1.0,2.0]
    sent=_capture(monkeypatch,[_ChatResponse(503),_ChatResponse(503),_ChatResponse(503),_ChatResponse()])
    assert llm.generate('y',PAYLOAD)==(None,'template') and len(sent)==3
    assert [r.status for r in usage_rows()][-3:]==['http_503','http_503','http_503']

def test_4xx_not_retried(monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','gemini'); monkeypatch.setattr(config,'LLM_API_KEY','bad'); monkeypatch.setattr(config,'LLM_MAX_RETRIES',3)
    sent=_capture(monkeypatch,[_ChatResponse(401)]*4)
    assert llm.generate('x',PAYLOAD)==(None,'template') and len(sent)==1 and llm.calls()[-1]['fallback_reason']=='http_401'

@pytest.mark.parametrize('scenario,reason,requests',[('quota','quota_exhausted',1),('rate_limit','rate_limited',1),('503','unavailable_503',3),('invalid_json','ValidationError',1)])
def test_fake_provider_scenarios(scenario,reason,requests,monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','fake'); monkeypatch.setattr(config,'LLM_FAKE_SCENARIO',scenario)
    monkeypatch.setattr(config,'LLM_MAX_RETRIES',0); monkeypatch.setattr(llm,'_sleep',lambda s:None)
    llm.reset_calls()
    with llm.call_budget(5) as scope:
        assert llm.generate('x',PAYLOAD)==(None,'template')
    assert llm.calls()[-1]['fallback_reason']==reason and scope['used']==requests==len(usage_rows())

def test_fake_503_once_then_success(monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','fake'); monkeypatch.setattr(config,'LLM_FAKE_SCENARIO','503_once')
    monkeypatch.setitem(llm._fake_state,'503_once',0); monkeypatch.setattr(llm,'_sleep',lambda s:None)
    assert llm.generate('x',PAYLOAD)[1]=='llm' and [r.status for r in usage_rows()]==['http_503','ok']

def test_daily_and_per_analysis_budget(monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','fake'); monkeypatch.setattr(config,'LLM_DAILY_BUDGET',2)
    assert llm.generate('a',PAYLOAD)[1]=='llm' and llm.generate('b',PAYLOAD)[1]=='llm'
    llm.reset_calls(); assert llm.generate('c',PAYLOAD)==(None,'template')
    assert llm.calls()[-1]['fallback_reason']=='daily_budget' and len(usage_rows())==2
    assert llm.status()['calls_today']==2 and llm.status()['daily_budget']==2
    monkeypatch.setattr(config,'LLM_DAILY_BUDGET',18)
    with llm.call_budget(1):
        assert llm.generate('d',PAYLOAD)[1]=='llm'
        llm.reset_calls(); assert llm.generate('e',PAYLOAD)==(None,'template')
        assert llm.calls()[-1]['fallback_reason']=='analysis_budget'

def test_analysis_uses_at_most_two_calls_and_cache(client,monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','fake'); monkeypatch.setattr(config,'AGENT_MODE','llm_plan')
    first=client.post('/api/incidents/INC-001/analyze').json()
    assert first['investigation']['mode']=='llm_plan' and first['text_source']=='llm'
    assert first['llm_usage']['requests']==2 and len(usage_rows())==2
    again=client.post('/api/incidents/INC-001/analyze').json()   # identical input: plan + wording from cache
    assert again['llm_usage']=={**again['llm_usage'],'requests':0,'cache_hits':2} and len(usage_rows())==2
    assert [(h['category'],h['score']) for h in again['hypotheses']]==[(h['category'],h['score']) for h in first['hypotheses']]
    stored=client.get('/api/analyses/'+first['run_id'])   # re-opening never calls the LLM
    assert stored.status_code==200 and len(usage_rows())==2
    monkeypatch.setattr(config,'AGENT_MODE','deterministic');monkeypatch.setattr(config,'LLM_FAKE_SCENARIO','quota')
    db_count=len(usage_rows())
    r=client.post('/api/incidents/INC-002/analyze').json()
    assert r['text_source']=='template' and r['llm_usage']['fallback_reason']=='quota_exhausted' and len(usage_rows())==db_count+1
    monkeypatch.setattr(config,'LLM_API_KEY','sk-test-secret-value')
    s=client.get('/api/llm/status').json();assert s['calls_today']==db_count+1 and s['blocked_until'] and 'sk-test-secret-value' not in json.dumps(s)

def test_key_resolution_b1():
    from backend.core.config import resolve_llm_key
    assert resolve_llm_key('gemini','  k1 ','g') == ('k1','LLM_API_KEY')
    assert resolve_llm_key('groq','','g1') == ('g1','GROQ_API_KEY')
    assert resolve_llm_key('groq','   ','g1') == ('g1','GROQ_API_KEY')
    assert resolve_llm_key('openai_compatible','','g1') == ('',None)
    assert resolve_llm_key('gemini',None,'') == ('',None)


def test_plan_503_fails_fast_and_wording_keeps_budget(client,monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','fake'); monkeypatch.setattr(config,'AGENT_MODE','llm_plan')
    monkeypatch.setattr(config,'LLM_FAKE_SCENARIO','503_once'); monkeypatch.setitem(llm._fake_state,'503_once',0)
    monkeypatch.setattr(llm,'_sleep',lambda s:None)
    r=client.post('/api/incidents/INC-001/analyze').json()
    assert r['investigation']['mode']=='deterministic' and r['text_source']=='llm'   # plan gave up after one 503, wording succeeded
    assert [x.status for x in usage_rows()]==['http_503','ok'] and r['llm_usage']['requests']==2
