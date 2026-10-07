"""Timezone-aware timestamps (B14), JSONB, pgvector vector(384) + HNSW, full-text tsvector + GIN.

On SQLite only existing ISO timestamp strings are normalised (SQLite does not enforce column types).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TIMESTAMPS = [("documents", "uploaded_at"), ("cases", "created_at"), ("analysis_runs", "created_at"),
              ("audit_log", "created_at"), ("eval_runs", "created_at")]
JSON_COLUMNS = [("machines", "data"), ("documents", "targets"), ("documents", "detection"), ("cases", "data"),
                ("analysis_runs", "response"), ("analysis_runs", "config"), ("analysis_runs", "llm_calls"),
                ("agent_traces", "args"), ("agent_traces", "result_summary"), ("agent_traces", "latency_ms"),
                ("agent_traces", "tokens"), ("audit_log", "data"), ("eval_runs", "config"), ("eval_runs", "result"),
                ("eval_results", "data")]
TSV_COLUMN = ("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS tsv tsvector "
              "GENERATED ALWAYS AS (to_tsvector('english', text)) STORED")


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        for table, column in TIMESTAMPS:
            op.alter_column(table, column, type_=sa.DateTime(timezone=True),
                            postgresql_using=f"NULLIF({column}, '')::timestamptz")
        for table, column in JSON_COLUMNS:
            op.alter_column(table, column, type_=JSONB(), postgresql_using=f"{column}::jsonb")
        # Old JSON vectors were optional and model-dependent; re-embed with `python -m backend.embed_chunks`.
        op.execute("UPDATE document_chunks SET embedding = NULL, embedding_model = NULL")
        op.alter_column("document_chunks", "embedding", type_=Vector(384), postgresql_using="NULL::vector(384)")
        op.create_index("ix_document_chunks_embedding_hnsw", "document_chunks", ["embedding"],
                        postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"})
        op.execute(TSV_COLUMN)
        op.execute("CREATE INDEX IF NOT EXISTS ix_document_chunks_tsv ON document_chunks USING gin (tsv)")
        return
    # SQLite: column types are not enforced, and a batch rebuild would CAST the text to a number.
    # Only rewrite ISO-8601 strings into SQLAlchemy's DateTime storage format; the ORM type does the rest.
    for table, column in TIMESTAMPS:
        rows = bind.execute(sa.text(f"SELECT rowid, {column} FROM {table} WHERE {column} IS NOT NULL")).all()
        for rowid, value in rows:
            parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            bind.execute(sa.text(f"UPDATE {table} SET {column} = :v WHERE rowid = :r"),
                         {"v": parsed.strftime("%Y-%m-%d %H:%M:%S.%f"), "r": rowid})


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_tsv")
        op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS tsv")
        op.drop_index("ix_document_chunks_embedding_hnsw", table_name="document_chunks")
        op.alter_column("document_chunks", "embedding", type_=sa.JSON(), postgresql_using="NULL::json")
        for table, column in JSON_COLUMNS:
            op.alter_column(table, column, type_=sa.JSON(), postgresql_using=f"{column}::json")
        for table, column in TIMESTAMPS:
            op.alter_column(table, column, type_=sa.String(), postgresql_using=f"to_char({column} AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"+00:00\"')")
        return
    # SQLite values stay readable as text; nothing to undo.
