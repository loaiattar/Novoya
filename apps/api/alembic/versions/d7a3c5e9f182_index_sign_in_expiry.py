"""index sessions.absolute_expires_at and one_time_tokens.expires_at

Revision ID: d7a3c5e9f182
Revises: eb491039487f
Create Date: 2026-10-22 23:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7a3c5e9f182"
down_revision: str | Sequence[str] | None = "eb491039487f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_sessions_absolute_expires_at", "sessions", ["absolute_expires_at"], unique=False
    )
    op.create_index(
        "ix_one_time_tokens_expires_at", "one_time_tokens", ["expires_at"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_one_time_tokens_expires_at", table_name="one_time_tokens")
    op.drop_index("ix_sessions_absolute_expires_at", table_name="sessions")
