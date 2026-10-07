from pathlib import Path
Path(".cache").mkdir(exist_ok=True)
import secrets
import pytest
import bcrypt
from sqlalchemy.orm import sessionmaker
from backend import db
from backend.core import config
from backend.init_db import init_db
from backend.auth import issue_token

TEST_PASSWORD=secrets.token_urlsafe(18)
TEST_HASH=bcrypt.hashpw(TEST_PASSWORD.encode(),bcrypt.gensalt(rounds=4)).decode()

@pytest.fixture
def test_password():
    return TEST_PASSWORD

@pytest.fixture(autouse=True)
def isolated_db(tmp_path,monkeypatch):
    engine=db.make_engine('sqlite:///'+str(tmp_path/'app.db'))
    monkeypatch.setattr(db,'engine',engine)
    monkeypatch.setattr(db,'Session',sessionmaker(bind=engine,expire_on_commit=False))
    monkeypatch.setattr(config,'JWT_SECRET',secrets.token_urlsafe(48))
    monkeypatch.setattr(config,'DOCUMENTS_DIR',tmp_path/'documents')
    monkeypatch.setattr(config,'LLM_CACHE_DIR',tmp_path/'llm_cache')
    for name in ('SEED_ADMIN_EMAIL','SEED_ADMIN_PASSWORD','DEMO_USERS_ENABLED'):
        monkeypatch.delenv(name,raising=False)
    init_db()
    with db.Session.begin() as session:
        for role in ('admin','engineer','qa_lead','viewer'):
            session.add(db.User(id=role,email=role+'@demo.local',password_hash=TEST_HASH,role=role,active=True,token_version=0))
    yield
    engine.dispose()

@pytest.fixture
def tokens():
    with db.Session() as session:
        return {role:issue_token(session.get(db.User,role)) for role in ('admin','engineer','qa_lead','viewer')}

@pytest.fixture
def client(tokens):
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app,raise_server_exceptions=False,headers={'Authorization':'Bearer '+tokens['admin']})
