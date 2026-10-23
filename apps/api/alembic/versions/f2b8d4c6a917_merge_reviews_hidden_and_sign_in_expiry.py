"""merge the reviews hidden and sign-in expiry index heads

Revision ID: f2b8d4c6a917
Revises: c4e8a1b7d902, d7a3c5e9f182
Create Date: 2026-10-23 00:10:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "f2b8d4c6a917"
down_revision: str | Sequence[str] | None = ("c4e8a1b7d902", "d7a3c5e9f182")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
