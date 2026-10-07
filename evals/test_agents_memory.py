from backend.core import config
from engine.memory import all_cases,recall
from engine import llm

def test_agent_trace_shapes_caps_and_denial(client,monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','groq');monkeypatch.setattr(config,'LLM_API_KEY','')
    result=client.post('/api/incidents/INC-001/analyze').json()
    assert result['investigation']['mode']=='deterministic'
    trace=client.get('/api/analyses/'+result['run_id']+'/trace').json()
    assert 0<len(trace)<=config.AGENT_MAX_STEPS and all(t['result_summary']['status']=='ok' for t in trace)
    assert any(t['tool']=='read_document_chunk' for t in trace)
    monkeypatch.setattr(config,'LLM_PROVIDER','fake')
    fake=client.post('/api/incidents/INC-001/analyze').json()
    assert fake['investigation']['mode']=='deterministic'   # default AGENT_MODE: no LLM planning
    monkeypatch.setattr(config,'AGENT_MODE','llm_plan')
    fake=client.post('/api/incidents/INC-001/analyze').json()
    assert fake.keys()==result.keys() and fake['investigation']['mode']=='llm_plan' and fake['investigation']['plan_source']=='llm'
    assert [(h['category'],h['score']) for h in fake['hypotheses']]==[(h['category'],h['score']) for h in result['hypotheses']]
    monkeypatch.setattr(config,'AGENT_MAX_STEPS',2)
    assert client.post('/api/incidents/INC-001/analyze').json()['investigation']['steps']==2
    original=llm.request_json
    def malicious(system,payload,schema,**kwargs):
        if schema.__name__=='ToolPlan':return {'steps':[{'tool':'search_machine_documents','args':{'machine_uid':'LINE-C/IMM-01','query':'cooling'}},
                                                         {'tool':'get_machine','args':{'machine_uid':'LINE-B/IMM-02'}},{'tool':'finish','args':{}}]}
        return original(system,payload,schema,**kwargs)
    monkeypatch.setattr(llm,'request_json',malicious)
    monkeypatch.setattr(config,'AGENT_MAX_STEPS',10)
    from sqlalchemy import delete
    from backend import db
    with db.Session.begin() as s:s.execute(delete(db.LLMCache))   # force a fresh (hostile) plan
    r=client.post('/api/incidents/INC-001/analyze').json()
    assert r['investigation']['denied_calls']==2 and r['investigation']['steps']==2
    assert [(h['category'],h['score']) for h in r['hypotheses']]==[(h['category'],h['score']) for h in result['hypotheses']]

def test_approval_current_exclusion_and_weighting(client,tokens):
    case={'incident_id':'INC-001','rca_draft':'draft','confirmed_category':'machine','confirmed_subcause':'cooling','fix_applied':'Inspected coolant circulation','lessons':'Verify before release','documents_used':['SOP-007']}
    client.headers['Authorization']='Bearer '+tokens['engineer']
    response=client.post('/api/cases',json=case);assert response.status_code==201,response.text
    cid=response.json()['case_id'];assert cid not in {c['case_id'] for c in all_cases()}
    assert client.post('/api/cases/'+cid+'/approve').status_code==403
    client.headers['Authorization']='Bearer '+tokens['qa_lead']
    assert client.post('/api/cases/'+cid+'/approve').status_code==200
    assert cid in {c['case_id'] for c in all_cases()}
    assert client.post('/api/cases/'+cid+'/reject').status_code==409
    saved=next(c for c in all_cases() if c['case_id']==cid)
    assert not any(c.case_id==cid for c in recall(saved['signals'],'INC-001',context=saved))
    matches=recall(saved['signals'],context=saved)
    assert matches[0].case_id==cid and matches[0].match_reasons
    assert all(c['label']=='synthetic seed' for c in all_cases() if c['case_id'].startswith('INC-H'))
