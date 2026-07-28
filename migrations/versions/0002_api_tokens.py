"""Encrypted API tokens and pipeline grants.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column("last_four", sa.String(4), nullable=False),
        sa.Column("allow_read", sa.Boolean(), nullable=False),
        sa.Column("allow_write", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_id", "name", name="uq_token_owner_name"),
    )
    op.create_index("ix_api_tokens_owner_id", "api_tokens", ["owner_id"])
    op.create_table(
        "pipeline_token_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pipeline_id", sa.String(36), nullable=False),
        sa.Column("token_id", sa.String(36), nullable=False),
        sa.Column("binding", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("operation", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "operation IN ('read', 'write')",
            name="ck_pipeline_token_grant_operation",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_id"], ["pipelines.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["token_id"], ["api_tokens.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "pipeline_id",
            "binding",
            name="uq_pipeline_binding",
        ),
    )
    op.create_index(
        "ix_pipeline_token_grants_pipeline_id",
        "pipeline_token_grants",
        ["pipeline_id"],
    )
    op.create_index(
        "ix_pipeline_token_grants_token_id",
        "pipeline_token_grants",
        ["token_id"],
    )


def downgrade() -> None:
    op.drop_table("pipeline_token_grants")
    op.drop_table("api_tokens")
