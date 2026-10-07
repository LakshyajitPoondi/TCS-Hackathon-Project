"""Stage 3: incident registry and status, versioned drafts and exports, links, names, dashboard, B5/B6/B11/B12."""
import pandas as pd
from backend.core.config import WARNING
from backend.services.data_loader import list_incidents


def as_role(client, tokens, role):
    client.headers['Authorization'] = 'Bearer ' + tokens[role]
    return client


def upload_copy(client):
    csv = pd.read_csv('data/incidents/incident_004.csv').to_csv(index=False).encode()
    r = client.post('/api/incidents/upload', files={'file': ('line_b.csv', csv)})
    assert r.status_code == 200, r.text
    return r.json()['id']


def test_b5_uploaded_incidents_listed_with_label_and_never_in_evals(client):
    uid = upload_copy(client)
    rows = client.get('/api/incidents').json()
    by_id = {r['id']: r for r in rows}
    assert by_id[uid]['source'] == 'uploaded' and by_id[uid]['source_label'] == 'Uploaded'
    assert by_id[uid]['uploaded_by_name'] == 'Admin' and by_id[uid]['machines'] and by_id[uid]['start_time']
    assert sum(r['source'] == 'sample' for r in rows) == 18 and by_id['INC-001']['source_label'] == 'Sample'
    assert by_id[uid]['status'] == 'new' and by_id[uid]['top_hypothesis'] is None
    assert uid not in {r['id'] for r in list_incidents()}   # evaluation set = sample files only


def test_status_transitions_drafts_cases_and_links(client, tokens):
    get = lambda: client.get('/api/incidents/INC-001/workflow').json()  # noqa: E731
    assert get()['status'] == 'new'
    run = as_role(client, tokens, 'engineer').post('/api/incidents/INC-001/analyze').json()
    w = get(); assert w['status'] == 'analysed' and w['top_hypothesis']['category'] == run['hypotheses'][0]['category']
    first = client.post('/api/incidents/INC-001/drafts', json={'content': 'Draft one.', 'run_id': run['run_id']})
    assert first.status_code == 201 and first.json()['version'] == 1 and first.json()['author_name'] == 'Engineer'
    assert client.post('/api/incidents/INC-001/drafts', json={'content': 'Draft two edited.'}).json()['version'] == 2
    assert get()['status'] == 'draft_saved' and get()['draft_version'] == 2
    restored = client.post('/api/incidents/INC-001/drafts/1/restore').json()
    assert restored['version'] == 3 and restored['content'] == 'Draft one.' and restored['note'] == 'Restored from version 1'
    versions = client.get('/api/incidents/INC-001/drafts').json()
    assert [d['version'] for d in versions] == [3, 2, 1]
    assert client.post('/api/incidents/INC-001/drafts', json={'content': '   '}).status_code == 422
    assert client.post('/api/incidents/INC-001/drafts', json={'content': 'x', 'run_id': 'not-a-run'}).status_code == 422
    case = client.post('/api/cases', json={'incident_id': 'INC-001', 'rca_draft': 'Draft one.', 'confirmed_category': 'machine',
                                           'confirmed_subcause': 'cooling', 'fix_applied': 'Cleaned chiller filter', 'documents_used': ['SOP-007']})
    assert case.status_code == 201
    w = get(); assert w['status'] == 'case_proposed' and w['cases'][0]['case_id'] == case.json()['case_id']
    assert w['cases'][0]['proposer_name'] == 'Engineer'
    listed = next(c for c in client.get('/api/cases').json() if c['case_id'] == case.json()['case_id'])
    assert listed['source_incident_id'] == 'INC-001' and listed['documents'] == [{'doc_id': 'SOP-007', 'title': 'Cooling System Troubleshooting'}]
    approved = as_role(client, tokens, 'qa_lead').post(f"/api/cases/{case.json()['case_id']}/approve").json()
    assert approved['approver_name'] == 'Qa Lead' and 'Approved by Qa Lead' in approved['summary']
    assert 'pending' not in approved['summary'] and 'awaiting' not in approved['summary']   # B6
    assert get()['status'] == 'case_approved'


def test_rejected_status(client, tokens):
    as_role(client, tokens, 'engineer')
    cid = client.post('/api/cases', json={'incident_id': 'INC-002', 'rca_draft': 'd', 'confirmed_category': 'material',
                                          'fix_applied': 'Quarantined lot'}).json()['case_id']
    as_role(client, tokens, 'qa_lead').post(f'/api/cases/{cid}/reject')
    assert client.get('/api/incidents/INC-002/workflow').json()['status'] == 'case_rejected'


def test_viewer_read_only_and_exports_keep_notice(client, tokens):
    as_role(client, tokens, 'engineer').post('/api/incidents/INC-003/drafts', json={'content': 'Draft without the notice → check ±2.'})
    viewer = as_role(client, tokens, 'viewer')
    assert viewer.post('/api/incidents/INC-003/drafts', json={'content': 'x'}).status_code == 403
    assert viewer.post('/api/incidents/INC-003/drafts/1/restore').status_code == 403
    assert viewer.get('/api/incidents/INC-003/drafts').json()[0]['content'].startswith('Draft without')
    md = viewer.get('/api/incidents/INC-003/drafts/1/export?format=md')
    assert md.status_code == 200 and 'attachment' in md.headers['content-disposition'] and md.text.count(WARNING) == 2
    pdf = viewer.get('/api/incidents/INC-003/drafts/1/export?format=pdf')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF') and pdf.headers['content-type'] == 'application/pdf'
    assert viewer.get('/api/incidents/INC-003/drafts/9/export').status_code == 404
    assert viewer.get('/api/incidents/INC-003/drafts/1/export?format=docx').status_code == 422


def test_b11_plant_documents_admin_only(client, tokens):
    eng = as_role(client, tokens, 'engineer')
    assert eng.patch('/api/documents/SOP-007', json={'scope': 'plant', 'targets': [], 'status': 'archived'}).status_code == 403
    assert eng.post('/api/documents/SOP-007/confirm', json={'scope': 'plant', 'targets': []}).status_code == 403
    doc = eng.post('/api/documents/upload', data={'title': 'Guide', 'doc_type': 'manual', 'scope': 'machine', 'targets': '["LINE-A/IMM-01"]'},
                   files={'file': ('g.md', b'# Guide\nLINE-A/IMM-01 coolant flow check.')}).json()
    assert eng.patch('/api/documents/' + doc['doc_id'], json={'scope': 'machine', 'targets': ['LINE-A/IMM-01'], 'status': 'archived'}).status_code == 200
    assert eng.patch('/api/documents/' + doc['doc_id'], json={'scope': 'plant', 'targets': []}).status_code == 403   # re-map to plant
    admin = as_role(client, tokens, 'admin')
    assert admin.patch('/api/documents/SOP-007', json={'scope': 'plant', 'targets': [], 'status': 'pending_mapping'}).status_code == 200


def test_b12_machine_incidents_by_affected_machine(client):
    rows = client.get('/api/machines/LINE-A/IMM-01/incidents').json()
    line_a = [r for r in client.get('/api/incidents').json() if r['line'] == 'LINE-A']
    assert rows and len(rows) < len(line_a)
    assert all('IMM-01' in r['affected_machines'] for r in rows)


def test_dashboard_and_nav_counts(client, tokens):
    as_role(client, tokens, 'engineer').post('/api/cases', json={'incident_id': 'INC-005', 'rca_draft': 'd', 'confirmed_category': 'method',
                                                                  'fix_applied': 'Reloaded setup sheet'})
    qa = as_role(client, tokens, 'qa_lead').get('/api/dashboard').json()
    assert qa['kpis']['cases_pending'] == 1 and qa['kpis']['incidents_total'] == 18
    assert set(qa['kpis']) >= {'incidents_by_status', 'documents_pending', 'llm_calls_today', 'llm_daily_budget'}
    assert any(p['kind'] == 'case_review' for p in qa['pending'])
    viewer = as_role(client, tokens, 'viewer').get('/api/dashboard').json()
    assert viewer['pending'] == [] and len(viewer['recent_incidents']) == 8
    assert client.get('/api/nav/counts').json() == {'documents_pending': 0, 'cases_pending': 1}
