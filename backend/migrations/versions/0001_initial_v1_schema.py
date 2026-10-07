"""Initial schema, identical to the v1 SQLite schema (String timestamps, JSON, JSON embeddings).

Revision ID: 0001
Revises:
Create Date: 2026-10-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False))
    op.create_table("machines",
        sa.Column("machine_uid", sa.String(), primary_key=True),
        sa.Column("short_name", sa.String(), nullable=False),
        sa.Column("line", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False))
    op.create_table("documents",
        sa.Column("doc_id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("targets", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("uploaded_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("uploaded_at", sa.String(), nullable=True),
        sa.Column("detection", sa.JSON(), nullable=True),
        sa.Column("storage_path", sa.String(), nullable=True))
    op.create_table("document_machine_links",
        sa.Column("doc_id", sa.String(), sa.ForeignKey("documents.doc_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("machine_uid", sa.String(), sa.ForeignKey("machines.machine_uid"), primary_key=True))
    op.create_table("document_chunks",
        sa.Column("chunk_id", sa.String(), primary_key=True),
        sa.Column("doc_id", sa.String(), sa.ForeignKey("documents.doc_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("page_or_section", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(), nullable=True))
    op.create_index("ix_document_chunks_doc_id", "document_chunks", ["doc_id"])
    op.create_table("cases",
        sa.Column("case_id", sa.String(), primary_key=True),
        sa.Column("source_incident_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("proposer_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approver_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False))
    op.create_index("ix_cases_source_incident_id", "cases", ["source_incident_id"])
    op.create_index("ix_cases_status", "cases", ["status"])
    op.create_table("analysis_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("incident_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("llm_calls", sa.JSON(), nullable=True))
    op.create_index("ix_analysis_runs_incident_id", "analysis_runs", ["incident_id"])
    op.create_table("agent_traces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(), nullable=False),
        sa.Column("args", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.JSON(), nullable=False),
        sa.Column("tokens", sa.JSON(), nullable=True))
    op.create_index("ix_agent_traces_run_id", "agent_traces", ["run_id"])
    op.create_table("audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False))
    op.create_table("eval_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False))
    op.create_table("eval_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("eval_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("suite", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False))
    op.create_table("revoked_tokens",
        sa.Column("jti", sa.String(), primary_key=True),
        sa.Column("expires", sa.Integer(), nullable=False))


def downgrade():
    for table in ("revoked_tokens", "eval_results", "eval_runs", "audit_log", "agent_traces", "analysis_runs",
                  "cases", "document_chunks", "document_machine_links", "documents", "machines", "users"):
        op.drop_table(table)
