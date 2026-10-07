from evals.run_evals import compute,persist
def test_all_deterministic_thresholds():
    result=compute()
    failed=[(s['suite'],m) for s in result['suites'] for m in s['metrics'] if m['passed'] is False]
    assert not failed,failed
    assert len(result['suites'])==9
def test_stored_evals_rbac(client,tokens,monkeypatch):
    from backend.api.routes import evals
    sample={'suites':[{'suite':'test','metrics':[{'metric':'probe','value':1,'threshold':1,'passed':True}],'details':[]}],'config':{'probe':True}}
    monkeypatch.setattr(evals,'compute',lambda:sample)
    for role in ('engineer','viewer'):
        assert client.post('/api/evals/run',headers={'Authorization':'Bearer '+tokens[role]}).status_code==403
    for role in ('admin','qa_lead'):
        r=client.post('/api/evals/run',headers={'Authorization':'Bearer '+tokens[role]});assert r.status_code==200,r.text
    assert client.get('/api/evals').json()['suites'][0]['suite']=='test'
