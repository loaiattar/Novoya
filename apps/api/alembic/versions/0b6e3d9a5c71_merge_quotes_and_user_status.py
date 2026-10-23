"""merge the quotes and users status heads

Revision ID: 0b6e3d9a5c71
Revises: f5a9c3e81d47, f5d9c2b7e814
Create Date: 2026-10-22 14:00:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0b6e3d9a5c71"
down_revision: str | Sequence[str] | None = ("f5a9c3e81d47", "f5d9c2b7e814")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
