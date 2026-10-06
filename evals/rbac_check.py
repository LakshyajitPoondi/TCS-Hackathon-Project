"""Real HTTP endpoint × role matrix. Runs only in an isolated evaluation process."""
import json
import secrets
from datetime import datetime,timezone,timedelta
import jwt
import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import select,delete
from backend import db
from backend.core import config
from backend.auth import issue_token,PERMISSIONS
from backend.init_db import init_db

def run():
    init_db()
    from backend.main import app
    from backend.api.routes import evals as routes
    # A suite cannot recursively invoke itself. Only the computation callback is stubbed;
    # the actual run endpoint, JWT, permissions, database writes and auditing execute.
    original=routes.compute
    routes.compute=lambda **kw: {'suites':[],'config':{'matrix_probe':True}}
    client=TestClient(app,raise_server_exceptions=False)
    password=secrets.token_urlsafe(18);hashed=bcrypt.hashpw(password.encode(),bcrypt.gensalt(rounds=4)).decode()
    roles=['admin','engineer','qa_lead','viewer'];tokens={};users={}
    with db.Session.begin() as s:
        for role in roles:
            u=db.User(id='matrix-'+role,email='matrix-'+role+'@demo.local',role=role,password_hash=hashed,active=True,token_version=0);s.add(u);s.flush();users[role]=u;tokens[role]=issue_token(u)
            for action in ('approve','reject'):s.add(db.Case(case_id=action+'-'+role,status='proposed',proposer_id='matrix-admin',data={'label':'matrix proposal'}))
        s.add(db.User(id='matrix-target',email='matrix-target@demo.local',role='viewer',password_hash=hashed,active=True,token_version=0))
        s.flush()
        # Exercise create on an existing canonical identity, without inventing a machine.
        s.execute(delete(db.DocumentMachineLink).where(db.DocumentMachineLink.machine_uid=='LINE-C/IMM-03'))
        s.execute(delete(db.Machine).where(db.Machine.machine_uid=='LINE-C/IMM-03'))
    admin={'Authorization':'Bearer '+tokens['admin']}
    initial=client.post('/api/incidents/INC-001/analyze',headers=admin)
    assert initial.status_code==200,initial.text
    run_id=initial.json()['run_id']
    machine=client.get('/api/machines/LINE-A/IMM-01',headers=admin).json()
    csv=(config.INCIDENTS_DIR/'incident_001.csv').read_bytes()
    case={'incident_id':'INC-001','rca_draft':'draft','confirmed_category':'machine','confirmed_subcause':'cooling','fix_applied':'Inspected cooling circuit'}
    entries=[('GET','/','view',{}),('GET','/api/auth/me','view',{}),('GET','/api/incidents','view',{}),('GET','/api/incidents/INC-001','view',{}),('GET','/api/incidents/INC-001/signals','view',{}),
      ('GET','/api/machines','view',{}),('GET','/api/machines/LINE-A/IMM-01','view',{}),('GET','/api/machines/LINE-A/IMM-01/documents','view',{}),('GET','/api/machines/LINE-A/IMM-01/incidents','view',{}),
      ('GET','/api/documents','view',{}),('GET','/api/documents/SOP-007','view',{}),('GET','/api/sops/SOP-007','view',{}),('GET','/api/cases','view',{}),('GET','/api/analyses','view',{}),('GET','/api/analyses/'+run_id,'view',{}),('GET','/api/analyses/'+run_id+'/trace','view',{}),('GET','/api/evals','view',{}),('GET','/api/users','users',{}),
      ('POST','/api/incidents/INC-001/analyze','analyze',{}),('POST','/api/incidents/upload','upload',{'files':{'file':('incident.csv',csv)}}),
      ('POST','/api/machines','machines',{'json':{**machine,'machine_uid':'LINE-C/IMM-03','short_name':'IMM-03','line':'LINE-C'}}),('PATCH','/api/machines/LINE-A/IMM-01','machines',{'json':machine}),
      ('POST','/api/documents/upload','documents',{'data':{'title':'Matrix guide','doc_type':'manual','scope':'plant'},'files':{'file':('guide.txt',b'Inspect coolant flow.')}}),
      ('PATCH','/api/documents/SOP-007','documents',{'json':{'scope':'plant','targets':[],'status':'pending_mapping'}}),('POST','/api/documents/SOP-007/confirm','documents',{'json':{'scope':'plant','targets':[]}}),
      ('POST','/api/cases','propose',{'json':case}),('POST','/api/cases/propose','propose',{'json':case}),('POST','/api/cases/approve-{role}/approve','approve',{}),('POST','/api/cases/reject-{role}/reject','approve',{}),
      ('POST','/api/evals/run','evals',{}),('POST','/api/users','users',{'json':{'email':'created@demo.local','password':password,'role':'viewer'}}),('PATCH','/api/users/matrix-target','users',{'json':{'active':True}}),
      ('POST','/api/auth/logout','view',{})]
    details=[]
    try:
        for method,path,permission,kwargs in entries:
            anonymous=client.request(method,path.replace('{role}','admin'),**kwargs)
            details.append({'method':method,'endpoint':path,'role':'anonymous','expected':401,'actual':anonymous.status_code,'passed':anonymous.status_code==401})
            for role in roles:
                r=client.request(method,path.replace('{role}',role),headers={'Authorization':'Bearer '+tokens[role]},**kwargs)
                expected=200 if role in PERMISSIONS[permission] else 403
                actual=200 if 200<=r.status_code<300 else r.status_code
                details.append({'method':method,'endpoint':path,'role':role,'expected':expected,'actual':r.status_code,'passed':actual==expected})
        for path in ('/health','/docs','/openapi.json'):
            r=client.get(path);details.append({'endpoint':path,'role':'anonymous','expected':200,'actual':r.status_code,'passed':r.status_code==200})
        r=client.post('/api/auth/login',json={'email':users['engineer'].email,'password':password});details.append({'endpoint':'/api/auth/login','actual':r.status_code,'passed':r.status_code==200})
        expired=jwt.encode({'sub':users['viewer'].id,'ver':0,'jti':'expiry-probe','iat':datetime.now(timezone.utc)-timedelta(days=1),'exp':datetime.now(timezone.utc)-timedelta(minutes=1)},config.JWT_SECRET,algorithm='HS256')
        r=client.get('/api/incidents',headers={'Authorization':'Bearer '+expired});details.append({'probe':'expiry','actual':r.status_code,'passed':r.status_code==401})
        fresh=issue_token(users['viewer'])
        with db.Session.begin() as s:s.get(db.User,users['viewer'].id).active=False
        r=client.get('/api/incidents',headers={'Authorization':'Bearer '+fresh});details.append({'probe':'deactivation','actual':r.status_code,'passed':r.status_code==401})
        with db.Session() as s:
            details.append({'probe':'mutation_audit_actor','passed':all(a.user_id for a in s.scalars(select(db.AuditLog)))})
    finally:routes.compute=original
    return details
if __name__=='__main__':print(json.dumps(run()))
