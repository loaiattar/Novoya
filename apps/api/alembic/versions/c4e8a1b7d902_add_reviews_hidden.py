"""add hidden on reviews

The admin's switch to take a published review down at once (#129). The DÉTOUR import
never writes this column (ADR 0014): it still deletes a review that left avis_diffusables.

Revision ID: c4e8a1b7d902
Revises: eb491039487f
Create Date: 2026-10-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4e8a1b7d902"
down_revision: str | Sequence[str] | None = "eb491039487f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column("hidden", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("reviews", "hidden")
