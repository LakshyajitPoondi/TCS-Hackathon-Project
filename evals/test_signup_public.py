"""Stage 6: public login config (demo profiles) and sign-up as an inactive viewer."""
from backend.core import config


def test_public_config_hides_demo_password_unless_demo_mode(client, monkeypatch):
    anon = client.get('/api/public/config', headers={'Authorization': ''})
    assert anon.status_code == 200 and anon.json()['demo_users_enabled'] is False and anon.json()['demo_profiles'] == []
    monkeypatch.setenv('DEMO_USERS_ENABLED', 'true'); monkeypatch.setenv('DEMO_PASSWORD', 'demo-pass-123')
    profiles = client.get('/api/public/config').json()['demo_profiles']
    assert [p['role'] for p in profiles] == ['admin', 'engineer', 'qa_lead', 'viewer']
    assert profiles[0]['email'] == 'demo-admin@demo.local' and all(p['password'] == 'demo-pass-123' for p in profiles)
    monkeypatch.setattr(config, 'APP_ENV', 'production')
    assert all('password' not in p for p in client.get('/api/public/config').json()['demo_profiles'])


def test_demo_seed_creates_demo_admin(monkeypatch):
    from sqlalchemy import select
    from backend import db
    from backend.auth import seed_users
    monkeypatch.setenv('DEMO_USERS_ENABLED', 'true'); monkeypatch.setenv('DEMO_PASSWORD', 'demo-pass-123')
    seed_users()
    with db.Session() as s:
        admin = s.scalar(select(db.User).where(db.User.email == 'demo-admin@demo.local'))
        assert admin.role == 'admin' and admin.active and admin.name == 'Administrator'


def test_signup_inactive_viewer_then_admin_activates(client, tokens):
    anon = {'Authorization': ''}
    r = client.post('/api/auth/signup', headers=anon, json={'name': 'New Operator', 'email': 'New@Plant.local', 'password': 'long-enough-1'})
    assert r.status_code == 201 and r.json()['status'] == 'pending_activation'
    assert client.post('/api/auth/signup', headers=anon, json={'name': 'Again', 'email': 'new@plant.local', 'password': 'long-enough-1'}).status_code == 409
    assert client.post('/api/auth/signup', headers=anon, json={'name': 'Short', 'email': 'x@plant.local', 'password': 'short'}).status_code == 422
    assert client.post('/api/auth/signup', headers=anon, json={'name': 'Bad', 'email': 'not-an-email', 'password': 'long-enough-1'}).status_code == 422
    login = client.post('/api/auth/login', headers=anon, json={'email': 'new@plant.local', 'password': 'long-enough-1'})
    assert login.status_code == 403 and 'pending activation' in login.json()['detail']
    assert client.post('/api/auth/login', headers=anon, json={'email': 'new@plant.local', 'password': 'wrong-password'}).status_code == 401
    users = client.get('/api/users').json()
    new = next(u for u in users if u['email'] == 'new@plant.local')
    assert new['active'] is False and new['role'] == 'viewer' and new['name'] == 'New Operator'
    assert client.get('/api/nav/counts').json()['users_pending'] == 1
    assert any(p['kind'] == 'user_activation' for p in client.get('/api/dashboard').json()['pending'])
    assert client.patch('/api/users/' + new['id'], json={'active': True}).status_code == 200
    ok = client.post('/api/auth/login', headers=anon, json={'email': 'new@plant.local', 'password': 'long-enough-1'})
    assert ok.status_code == 200 and ok.json()['user']['role'] == 'viewer'
