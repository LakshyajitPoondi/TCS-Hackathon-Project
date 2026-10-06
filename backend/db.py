"""SQLite persistence. Every mutation uses one transaction, never read/rewrite JSON."""
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, Column, String, Integer, Boolean, JSON, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.core import config

Base = declarative_base()

def now():
    return datetime.now(timezone.utc).isoformat()

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    token_version = Column(Integer, default=0, nullable=False)

class Machine(Base):
    __tablename__ = "machines"
    machine_uid = Column(String, primary_key=True)
    short_name = Column(String, nullable=False)
    line = Column(String, nullable=False)
    model = Column(String, nullable=False)
    data = Column(JSON, nullable=False)

class Document(Base):
    __tablename__ = "documents"
    doc_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    doc_type = Column(String, nullable=False)
    version = Column(String, default="1", nullable=False)
    scope = Column(String, nullable=False)
    targets = Column(JSON, default=list, nullable=False)
    status = Column(String, nullable=False)
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(String, default=now)
    detection = Column(JSON, default=dict)
    storage_path = Column(String, nullable=True)

class DocumentMachineLink(Base):
    __tablename__ = "document_machine_links"
    doc_id = Column(String, ForeignKey("documents.doc_id", ondelete="CASCADE"), primary_key=True)
    machine_uid = Column(String, ForeignKey("machines.machine_uid"), primary_key=True)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    chunk_id = Column(String, primary_key=True)
    doc_id = Column(String, ForeignKey("documents.doc_id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String, nullable=False)
    page_or_section = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)
    embedding_model = Column(String, nullable=True)

class Case(Base):
    __tablename__ = "cases"
    case_id = Column(String, primary_key=True)
    source_incident_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, index=True)
    proposer_id = Column(String, ForeignKey("users.id"), nullable=True)
    approver_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(String, default=now)
    data = Column(JSON, nullable=False)

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    run_id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(String, default=now)
    response = Column(JSON, nullable=False)
    config = Column(JSON, default=dict)
    llm_calls = Column(JSON, default=list)

class AgentTrace(Base):
    __tablename__ = "agent_traces"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    step = Column(Integer, nullable=False)
    tool = Column(String, nullable=False)
    args = Column(JSON, nullable=False)
    result_summary = Column(JSON, nullable=False)
    latency_ms = Column(JSON, nullable=False)
    tokens = Column(JSON, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    created_at = Column(String, default=now)
    data = Column(JSON, nullable=False)

class EvalRun(Base):
    __tablename__ = "eval_runs"
    run_id = Column(String, primary_key=True)
    created_at = Column(String, default=now)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    config = Column(JSON, nullable=False)
    result = Column(JSON, nullable=False)

class EvalResult(Base):
    __tablename__ = "eval_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("eval_runs.run_id", ondelete="CASCADE"), nullable=False)
    suite = Column(String, nullable=False)
    data = Column(JSON, nullable=False)

class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    jti = Column(String, primary_key=True)
    expires = Column(Integer, nullable=False)

def make_engine(url):
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout":30} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def sqlite_setup(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")
    return engine

engine = make_engine(config.DATABASE_URL)
Session = sessionmaker(bind=engine, expire_on_commit=False)

def audit(session, user_id, action, data):
    session.add(AuditLog(user_id=user_id, action=action, data=data))
