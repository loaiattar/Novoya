"""merge the super admin and quotes answer heads

Revision ID: eb491039487f
Revises: c1e8f4a2b693, c4e8a2f61d93
Create Date: 2026-10-22 20:07:10.894826

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "eb491039487f"
down_revision: str | Sequence[str] | None = ("c1e8f4a2b693", "c4e8a2f61d93")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
