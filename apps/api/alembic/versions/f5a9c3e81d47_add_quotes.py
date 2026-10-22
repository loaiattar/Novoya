"""add quotes

Revision ID: f5a9c3e81d47
Revises: a3c7e5f91b26
Create Date: 2026-10-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f5a9c3e81d47"
down_revision: str | Sequence[str] | None = "a3c7e5f91b26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quotes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("total_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("locale", sa.String(length=2), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pdf", sa.LargeBinary(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_comment", sa.Text(), nullable=True),
        sa.CheckConstraint("total_price > 0", name="ck_quotes_total_price"),
        sa.CheckConstraint("locale IN ('en', 'fr')", name="ck_quotes_locale"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number", name="uq_quotes_number"),
        sa.UniqueConstraint("plan_id", name="uq_quotes_plan_id"),
    )
    op.create_index("ix_quotes_client_id", "quotes", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_quotes_client_id", table_name="quotes")
    op.drop_table("quotes")
