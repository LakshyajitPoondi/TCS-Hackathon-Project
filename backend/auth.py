"""Server-side RBAC; current user/role/status checked on every request."""
import os
import uuid
import secrets
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend import db
from backend.core import config

ROLES = {"admin", "engineer", "qa_lead", "viewer"}
PERMISSIONS = {"view":ROLES, "analyze":{"admin","engineer","qa_lead"}, "upload":{"admin","engineer"},
    "machines":{"admin"}, "documents":{"admin","engineer"}, "propose":{"admin","engineer"},
    "approve":{"admin","qa_lead"}, "evals":{"admin","qa_lead"}, "users":{"admin"},
    "draft":{"admin","engineer","qa_lead"}, "plant_documents":{"admin"}}
_development_secret = secrets.token_urlsafe(48)
DEMO_PROFILES=[('demo-admin','admin'),('engineer','engineer'),('qa','qa_lead'),('viewer','viewer')]
DEMO_LABELS={'admin':'Administrator','engineer':'Plant engineer','qa_lead':'QA lead','viewer':'Viewer'}

def demo_enabled():
    return os.getenv("DEMO_USERS_ENABLED","false").lower()=="true" and bool(os.getenv("DEMO_PASSWORD",""))

def demo_profiles():
    """Public demo profiles for the login page. The password is included only in demo mode and never outside
    APP_ENV=development, so a production bundle or API never carries it."""
    if not demo_enabled():
        return []
    expose=config.APP_ENV=="development"
    return [{"label":DEMO_LABELS[role],"role":role,"email":f"{name}@demo.local",**({"password":os.getenv("DEMO_PASSWORD","")} if expose else {})}
            for name,role in DEMO_PROFILES]
bearer = HTTPBearer(auto_error=False)

def secret():
    if config.JWT_SECRET:
        if len(config.JWT_SECRET) < 32:
            raise HTTPException(503, "JWT_SECRET must have at least 32 characters")
        return config.JWT_SECRET
    if config.APP_ENV != "development":
        raise HTTPException(503, "JWT_SECRET is required outside development")
    return _development_secret

def hash_password(password):
    raw=password.encode()
    if len(raw)>72 or len(raw)<10:
        raise HTTPException(422,"Password must be 10–72 UTF-8 bytes")
    return bcrypt.hashpw(raw,bcrypt.gensalt()).decode()

def public_user(user):
    from backend.services.workflow import display_name
    return {"id":user.id,"email":user.email,"name":display_name(user),"role":user.role,"active":user.active}

def issue_token(user):
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":user.id,"ver":user.token_version,"jti":uuid.uuid4().hex,"iat":now,"exp":now+timedelta(minutes=config.JWT_EXPIRE_MINUTES)},secret(),algorithm="HS256")

def token_claims(token):
    try:
        return jwt.decode(token,secret(),algorithms=["HS256"],options={"require":["sub","exp","iat","jti","ver"]})
    except jwt.InvalidTokenError:
        raise HTTPException(401,"Invalid or expired token",headers={"WWW-Authenticate":"Bearer"})

def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer)):
    if not credentials:
        raise HTTPException(401,"Authentication required",headers={"WWW-Authenticate":"Bearer"})
    claims=token_claims(credentials.credentials)
    with db.Session() as session:
        user=session.get(db.User,claims["sub"])
        if not user or not user.active or user.token_version != claims['ver'] or session.get(db.RevokedToken,claims['jti']):
            raise HTTPException(401,"Inactive user or revoked session")
        return user

def require(action):
    def permission(user=Depends(current_user)):
        if user.role not in PERMISSIONS[action]:
            raise HTTPException(403,"Permission denied")
        return user
    return permission

def seed_users():
    email=os.getenv("SEED_ADMIN_EMAIL","").strip().lower()
    password=os.getenv("SEED_ADMIN_PASSWORD","")
    profiles=[(email,password,"admin")] if email and password else []
    if os.getenv("DEMO_USERS_ENABLED","false").lower()=="true":
        demo=os.getenv("DEMO_PASSWORD","")
        if not demo: raise ValueError("DEMO_PASSWORD required when demo users enabled")
        # A separate demo admin backs the login page's admin demo button; the real seed admin password is never exposed.
        profiles += [(f"{name}@demo.local",demo,role) for name,role in DEMO_PROFILES]
    names={'admin':'Administrator','engineer':'Plant Engineer','qa_lead':'QA Lead','viewer':'Viewer'}
    from sqlalchemy import select
    with db.Session.begin() as session:
        for email,password,role in profiles:
            if not session.scalar(select(db.User).where(db.User.email==email)):
                user=db.User(id=uuid.uuid4().hex,email=email,name=names[role],password_hash=hash_password(password),role=role,active=True,token_version=0)
                session.add(user); session.flush()
                db.audit(session,user.id,"seed_user",{"email":email,"role":role})
