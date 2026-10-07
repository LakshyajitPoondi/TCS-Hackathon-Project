"""LLM usage log (daily budget, quota blocks) and DB-backed LLM output cache.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _json():
    return sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade():
    op.create_table("llm_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("day", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("tokens", _json(), nullable=True),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_llm_usage_day", "llm_usage", ["day"])
    op.create_table("llm_cache",
        sa.Column("cache_key", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("incident_id", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("output", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_llm_cache_incident_id", "llm_cache", ["incident_id"])


def downgrade():
    op.drop_table("llm_cache")
    op.drop_table("llm_usage")
