"""add plans.custom and plans.agent_outline (custom requests, #184)

Revision ID: c7e4a1d9b352
Revises: b3f6d2a8c417
Create Date: 2026-10-23 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e4a1d9b352"
down_revision: str | Sequence[str] | None = "b3f6d2a8c417"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "plans",
        sa.Column("custom", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("plans", sa.Column("agent_outline", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("plans", "agent_outline")
    op.drop_column("plans", "custom")
