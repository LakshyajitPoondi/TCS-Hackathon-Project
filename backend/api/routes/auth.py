import uuid
import bcrypt
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from backend import db
from backend.auth import current_user, require, public_user, issue_token, hash_password, token_claims, bearer, ROLES

router=APIRouter(prefix="/api",tags=["authentication"])
class Login(BaseModel):
    email:str = Field(max_length=254)
    password:str = Field(max_length=72)

@router.post('/auth/login')
def login(body:Login):
    with db.Session.begin() as session:
        user=session.scalar(select(db.User).where(db.User.email==body.email.strip().lower()))
        valid=False
        if user and len(body.password.encode())<=72:
            valid=bcrypt.checkpw(body.password.encode(),user.password_hash.encode())
        if not valid or not user.active: raise HTTPException(401,"Invalid email or password")
        db.audit(session,user.id,"login",{})
        return {"access_token":issue_token(user),"token_type":"bearer","user":public_user(user)}

@router.get('/auth/me')
def me(user=Depends(current_user)):
    return public_user(user)

@router.post('/auth/logout')
def logout(user=Depends(current_user),credentials=Depends(bearer)):
    claims=token_claims(credentials.credentials)
    with db.Session.begin() as session:
        session.merge(db.RevokedToken(jti=claims['jti'],expires=claims['exp']))
        db.audit(session,user.id,"logout",{})
    return {"status":"logged_out"}

class NewUser(Login):
    role:str

@router.get('/users')
def users(user=Depends(require('users'))):
    with db.Session() as session: return [public_user(u) for u in session.scalars(select(db.User))]

@router.post('/users',status_code=201)
def create(body:NewUser,user=Depends(require('users'))):
    if body.role not in ROLES or '@' not in body.email: raise HTTPException(422,"Invalid role/email")
    with db.Session.begin() as session:
        if session.scalar(select(db.User).where(db.User.email==body.email.lower())): raise HTTPException(409,"Email exists")
        new=db.User(id=uuid.uuid4().hex,email=body.email.lower(),password_hash=hash_password(body.password),role=body.role,active=True,token_version=0)
        session.add(new); session.flush(); db.audit(session,user.id,'create_user',public_user(new))
        return public_user(new)

class EditUser(BaseModel):
    role:str|None=None
    active:bool|None=None

@router.patch('/users/{user_id}')
def update(user_id:str,body:EditUser,user=Depends(require('users'))):
    if body.role is not None and body.role not in ROLES: raise HTTPException(422,"Invalid role")
    if user_id==user.id and (body.active is False or body.role not in (None,'admin')): raise HTTPException(422,"Cannot remove your own admin access")
    with db.Session.begin() as session:
        target=session.get(db.User,user_id)
        if not target: raise HTTPException(404,"User not found")
        if body.role is not None: target.role=body.role
        if body.active is not None: target.active=body.active
        target.token_version+=1
        db.audit(session,user.id,'update_user',public_user(target))
        return public_user(target)
