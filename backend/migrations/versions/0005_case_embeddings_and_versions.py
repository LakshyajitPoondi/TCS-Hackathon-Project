"""Case summary embeddings (vector(384) on Postgres) and case version history.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-07
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    postgres = op.get_bind().dialect.name == "postgresql"
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("embedding", Vector(384) if postgres else sa.JSON(), nullable=True))
        batch.add_column(sa.Column("embedding_model", sa.String(), nullable=True))
    op.create_table("case_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(), sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("data", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("change", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("editor_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_case_versions_case_id", "case_versions", ["case_id"])


def downgrade():
    op.drop_table("case_versions")
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("embedding_model")
        batch.drop_column("embedding")
