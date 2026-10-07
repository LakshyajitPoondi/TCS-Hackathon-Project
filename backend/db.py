"""Database models and session. Postgres + pgvector by default; SQLite still works for tests.

Every mutation uses one transaction. Timestamps are timezone-aware (UTC). JSON columns become
JSONB on Postgres and embeddings become pgvector vector(384) with an HNSW cosine index.
"""
from datetime import datetime, timezone
from sqlalchemy import (create_engine, event, Column, String, Integer, Boolean, JSON, ForeignKey, Text,
                        DateTime, Index, DDL, Float)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.types import TypeDecorator
from pgvector.sqlalchemy import Vector
from backend.core import config

Base = declarative_base()
EMBEDDING_DIM = 384


def now():
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """timestamptz on Postgres; on SQLite naive values are read back as UTC."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class EmbeddingType(TypeDecorator):
    """vector(384) on Postgres, JSON list on SQLite. Always returns a plain list of floats."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(EMBEDDING_DIM))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        values = [float(v) for v in value]
        if dialect.name == "postgresql" and len(values) != EMBEDDING_DIM:
            raise ValueError(f"embedding must have {EMBEDDING_DIM} dimensions, got {len(values)}")
        return values

    def process_result_value(self, value, dialect):
        return None if value is None else [float(v) for v in value]


JSONType = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    token_version = Column(Integer, default=0, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(UTCDateTime, default=now)

class Machine(Base):
    __tablename__ = "machines"
    machine_uid = Column(String, primary_key=True)
    short_name = Column(String, nullable=False)
    line = Column(String, nullable=False)
    model = Column(String, nullable=False)
    data = Column(JSONType, nullable=False)

class Document(Base):
    __tablename__ = "documents"
    doc_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    doc_type = Column(String, nullable=False)
    version = Column(String, default="1", nullable=False)
    scope = Column(String, nullable=False)
    targets = Column(JSONType, default=list, nullable=False)
    status = Column(String, nullable=False)
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(UTCDateTime, default=now)
    detection = Column(JSONType, default=dict)
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
    embedding = Column(EmbeddingType, nullable=True)
    embedding_model = Column(String, nullable=True)

# Postgres-only: HNSW cosine index for vector search and a generated tsvector + GIN index for full-text search.
# The tsv column is not mapped; retrieval reads it through SQL on Postgres only.
Index("ix_document_chunks_embedding_hnsw", DocumentChunk.embedding, postgresql_using="hnsw",
      postgresql_ops={"embedding": "vector_cosine_ops"}).ddl_if(dialect="postgresql")
TSV_COLUMN_DDL = ("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS tsv tsvector "
                  "GENERATED ALWAYS AS (to_tsvector('english', text)) STORED")
TSV_INDEX_DDL = "CREATE INDEX IF NOT EXISTS ix_document_chunks_tsv ON document_chunks USING gin (tsv)"
event.listen(DocumentChunk.__table__, "after_create", DDL(TSV_COLUMN_DDL).execute_if(dialect="postgresql"))
event.listen(DocumentChunk.__table__, "after_create", DDL(TSV_INDEX_DDL).execute_if(dialect="postgresql"))

class Case(Base):
    __tablename__ = "cases"
    case_id = Column(String, primary_key=True)
    source_incident_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, index=True)
    proposer_id = Column(String, ForeignKey("users.id"), nullable=True)
    approver_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(UTCDateTime, default=now)
    data = Column(JSONType, nullable=False)

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    run_id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(UTCDateTime, default=now)
    response = Column(JSONType, nullable=False)
    config = Column(JSONType, default=dict)
    llm_calls = Column(JSONType, default=list)

class AgentTrace(Base):
    __tablename__ = "agent_traces"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    step = Column(Integer, nullable=False)
    tool = Column(String, nullable=False)
    args = Column(JSONType, nullable=False)
    result_summary = Column(JSONType, nullable=False)
    latency_ms = Column(JSONType, nullable=False)
    tokens = Column(JSONType, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    created_at = Column(UTCDateTime, default=now)
    data = Column(JSONType, nullable=False)

class EvalRun(Base):
    __tablename__ = "eval_runs"
    run_id = Column(String, primary_key=True)
    created_at = Column(UTCDateTime, default=now)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    config = Column(JSONType, nullable=False)
    result = Column(JSONType, nullable=False)

class EvalResult(Base):
    __tablename__ = "eval_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("eval_runs.run_id", ondelete="CASCADE"), nullable=False)
    suite = Column(String, nullable=False)
    data = Column(JSONType, nullable=False)

class Incident(Base):
    """Registry of sample (evaluation set) and uploaded incidents. Status is derived, never stored.
    start_time/end_time are the CSV's own clock (ISO text, no timezone)."""
    __tablename__ = "incidents"
    incident_id = Column(String, primary_key=True)
    source = Column(String, nullable=False)          # sample | uploaded
    filename = Column(String, nullable=False)
    line = Column(String, nullable=False)
    machines = Column(JSONType, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    record_count = Column(Integer, nullable=False)
    affected_machines = Column(JSONType, nullable=True)   # computed lazily from signals + hypothesis targets
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(UTCDateTime, default=now)

class RcaDraft(Base):
    """Every save is a new version; restore copies an old version into a new one."""
    __tablename__ = "rca_drafts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String, nullable=False, index=True)
    run_id = Column(String, ForeignKey("analysis_runs.run_id", ondelete="SET NULL"), nullable=True)
    version = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    note = Column(String, nullable=True)
    author_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(UTCDateTime, default=now)
    __table_args__ = (Index("uq_rca_drafts_incident_version", "incident_id", "version", unique=True),)

class LLMUsage(Base):
    """One row per provider request (including failed ones); the daily budget counts today's rows."""
    __tablename__ = "llm_usage"
    id = Column(Integer, primary_key=True, autoincrement=True)
    day = Column(String(10), nullable=False, index=True)
    created_at = Column(UTCDateTime, default=now)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    status = Column(String, nullable=False)
    http_status = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    tokens = Column(JSONType, nullable=True)
    blocked_until = Column(UTCDateTime, nullable=True)

class LLMCache(Base):
    """Validated LLM output keyed by kind + incident + analysis input hash + provider + model + prompt version."""
    __tablename__ = "llm_cache"
    cache_key = Column(String, primary_key=True)
    kind = Column(String, nullable=False)
    incident_id = Column(String, nullable=True, index=True)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)
    output = Column(JSONType, nullable=False)
    created_at = Column(UTCDateTime, default=now)

class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    jti = Column(String, primary_key=True)
    expires = Column(Integer, nullable=False)

def is_postgres(bind=None):
    return (bind or engine).dialect.name == "postgresql"

def make_engine(url):
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
        @event.listens_for(engine, "connect")
        def sqlite_setup(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")
        return engine
    return create_engine(url, pool_pre_ping=True)

engine = make_engine(config.DATABASE_URL)
Session = sessionmaker(bind=engine, expire_on_commit=False)

def audit(session, user_id, action, data):
    session.add(AuditLog(user_id=user_id, action=action, data=data))
