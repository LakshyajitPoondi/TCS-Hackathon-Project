"""Incident registry, versioned RCA drafts, user display names.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _json():
    return sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("name", sa.String(), nullable=True))
        batch.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table("incidents",
        sa.Column("incident_id", sa.String(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("line", sa.String(), nullable=False),
        sa.Column("machines", _json(), nullable=False),
        sa.Column("start_time", sa.String(), nullable=False),
        sa.Column("end_time", sa.String(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("affected_machines", _json(), nullable=True),
        sa.Column("uploaded_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table("rca_drafts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("incident_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("author_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_rca_drafts_incident_id", "rca_drafts", ["incident_id"])
    op.create_index("uq_rca_drafts_incident_version", "rca_drafts", ["incident_id", "version"], unique=True)


def downgrade():
    op.drop_table("rca_drafts")
    op.drop_table("incidents")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("created_at")
        batch.drop_column("name")
