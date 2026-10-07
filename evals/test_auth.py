import jwt
from datetime import datetime,timezone,timedelta
from fastapi.testclient import TestClient
from backend.main import app
from backend import db
from backend.core import config

def test_login_logout(client,test_password):
    r=client.post('/api/auth/login',json={'email':'engineer@demo.local','password':test_password})
    assert r.status_code==200
    token=r.json()['access_token'];h={'Authorization':'Bearer '+token}
    assert client.get('/api/auth/me',headers=h).json()['role']=='engineer'
    assert client.post('/api/auth/logout',headers=h).status_code==200
    assert client.get('/api/auth/me',headers=h).status_code==401
    assert client.post('/api/auth/login',json={'email':'engineer@demo.local','password':'wrong'}).status_code==401

def test_permissions(tokens):
    c=TestClient(app)
    assert c.get('/health').status_code==200
    assert c.get('/openapi.json').status_code==200
    assert c.get('/api/incidents').status_code==401
    for role,token in tokens.items():
        h={'Authorization':'Bearer '+token}
        assert c.get('/api/incidents',headers=h).status_code==200
        assert c.post('/api/incidents/INC-001/analyze',headers=h).status_code==(403 if role=='viewer' else 200)
        assert c.get('/api/users',headers=h).status_code==(200 if role=='admin' else 403)
        assert c.post('/api/incidents/upload',headers=h,files={'file':('bad.csv',b'x')}).status_code==(422 if role in ('admin','engineer') else 403)

def test_expiry_deactivation_and_management(client,tokens):
    expired=jwt.encode({'sub':'viewer','ver':0,'jti':'expired','iat':datetime.now(timezone.utc)-timedelta(days=1),'exp':datetime.now(timezone.utc)-timedelta(minutes=1)},config.JWT_SECRET,algorithm='HS256')
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+expired}).status_code==401
    assert client.patch('/api/users/viewer',json={'active':False}).status_code==200
    assert client.get('/api/incidents',headers={'Authorization':'Bearer '+tokens['viewer']}).status_code==401
    assert client.patch('/api/users/engineer',json={'role':'qa_lead'}).status_code==200
    assert client.get('/api/incidents',headers={'Authorization':'Bearer '+tokens['engineer']}).status_code==401
    assert client.patch('/api/users/admin',json={'active':False}).status_code==422
    from sqlalchemy import select
    with db.Session() as session:
        logs=list(session.scalars(select(db.AuditLog)))
        assert len(logs)>=2 and all(x.user_id=='admin' for x in logs)
