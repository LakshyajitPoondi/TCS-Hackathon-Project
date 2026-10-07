from engine.grounding import check_detailed
from backend.core import config
from engine import llm

def payload():return {'incident_id':'INC-007','kpis':{'alarm_count':7},'hypotheses':[{'rank':1,'supporting_evidence':[{'signal':'temperature_delta','machine':'IMM-01','value':10,'description':'Temperature on IMM-01 rose from 60 to 70.'}],
        'chunks':[{'doc_id':'SOP-007','chunk_id':'c1','text':'Check coolant flow.'}]}]}
def test_adversarial_numbers_direction_machine_and_action():
    def check(narrative,step='Check coolant flow.',chunk='c1'):
        return check_detailed({'hypotheses':[{'rank':1,'narrative':narrative,'verification_steps':[{'source':'SOP-007','chunk_id':chunk,'step':step}]}],'rca_draft':'Verification required.'},payload(),{1:['SOP-007']})
    assert check('Temperature on IMM-01 rose to 70.')[0].passed
    for text in ('Temperature fell to 7.','Temperature on IMM-02 rose to 70.','Temperature on IMM-01 fell to 70.','Temperature rose to 007.'):
        assert not check(text)[0].passed
    assert not check('Hypothesis requires verification.','Replace the entire machine immediately.')[0].passed
    assert not check('Hypothesis requires verification.',chunk='wrong')[0].passed
    p=payload();p['kpis']={}
    assert not check_detailed({'hypotheses':[],'rca_draft':'Temperature fell to 7.'},p,{})[0].passed

def test_replacement_and_abstention_checked(client,monkeypatch):
    monkeypatch.setattr(config,'LLM_PROVIDER','fake')
    original=llm.generate
    def hostile(i,p):
        out,source=original(i,p)
        for h in out['hypotheses']:
            h['narrative']='Temperature fell to 7.'
            h['verification_steps']=[{'source':'SOP-007','chunk_id':'wrong','step':'Replace the entire machine immediately.'}]
        return out,source
    monkeypatch.setattr(llm,'generate',hostile)
    r=client.post('/api/incidents/INC-001/analyze');assert r.status_code==200,r.text
    data=r.json();assert data['grounding']['flagged'] and any(s['replaced'] for s in data['grounding']['sections'])
    assert 'fell to 7' not in data['hypotheses'][0]['narrative']
    r=client.post('/api/incidents/INC-016/analyze');assert r.status_code==200,r.text
    assert r.json()['grounding']['sections']
