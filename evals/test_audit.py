"""Stage 7: audit-log viewer for administrators."""
from datetime import date, timedelta


def test_audit_filters_and_permissions(client, tokens):
    client.post('/api/incidents/INC-001/drafts', json={'content': 'audit probe'})
    new = client.post('/api/users', json={'email': 'audit@demo.local', 'password': 'long-enough-1', 'role': 'viewer'}).json()
    client.patch('/api/users/' + new['id'], json={'role': 'engineer'})
    full = client.get('/api/audit').json()
    assert full['total'] >= 2 and {'save_draft', 'update_user'} <= set(full['actions'])
    assert full['items'][0]['created_at'] >= full['items'][-1]['created_at'] and full['items'][0]['user_name'] == 'Admin'
    drafts = client.get('/api/audit?action=save_draft').json()
    assert drafts['total'] == 1 and drafts['items'][0]['data']['incident_id'] == 'INC-001'
    assert client.get('/api/audit?user_id=engineer').json()['total'] == 0
    today = date.today().isoformat()
    assert client.get(f'/api/audit?date_from={today}&date_to={today}').json()['total'] == full['total']
    tomorrow = (date.today() + timedelta(days=2)).isoformat()
    assert client.get(f'/api/audit?date_from={tomorrow}').json()['total'] == 0
    assert client.get('/api/audit?date_from=07-10-2026').status_code == 422
    page = client.get('/api/audit?limit=1&offset=1').json()
    assert len(page['items']) == 1 and page['items'][0]['id'] == full['items'][1]['id']
    for role in ('engineer', 'qa_lead', 'viewer'):
        assert client.get('/api/audit', headers={'Authorization': 'Bearer ' + tokens[role]}).status_code == 403
