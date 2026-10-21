"""add plan_extras

Revision ID: e8b13c5d7a40
Revises: d4f2a8c61e93
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8b13c5d7a40"
down_revision: str | Sequence[str] | None = "d4f2a8c61e93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_extras",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("extra_id", sa.Uuid(), nullable=False),
        sa.Column("pricing", sa.String(length=16), nullable=False),
        sa.Column("price_eur", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "pricing IN ('included', 'supplement', 'on_quote')", name="ck_plan_extras_pricing"
        ),
        sa.CheckConstraint("price_eur IS NULL OR price_eur > 0", name="ck_plan_extras_price"),
        sa.ForeignKeyConstraint(["extra_id"], ["extras.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("plan_id", "extra_id"),
    )


def downgrade() -> None:
    op.drop_table("plan_extras")
