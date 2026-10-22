"""add users status_changed_by and status_changed_at

Revision ID: f5d9c2b7e814
Revises: a3c7e5f91b26
Create Date: 2026-10-22 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5d9c2b7e814"
down_revision: str | Sequence[str] | None = "a3c7e5f91b26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("status_changed_by", sa.Uuid(), nullable=True))
    op.add_column(
        "users", sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_users_status_changed_by_users",
        "users",
        "users",
        ["status_changed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_users_status_changed_by_users", "users", type_="foreignkey")
    op.drop_column("users", "status_changed_at")
    op.drop_column("users", "status_changed_by")
