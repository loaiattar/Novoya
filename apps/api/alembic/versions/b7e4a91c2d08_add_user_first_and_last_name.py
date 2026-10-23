"""add user first_name and last_name

Revision ID: b7e4a91c2d08
Revises: 58aa3536140b
Create Date: 2026-10-21 11:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e4a91c2d08"
down_revision: str | Sequence[str] | None = "58aa3536140b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("first_name", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=100), nullable=True))
    op.execute(
        """
        UPDATE users
        SET
          first_name = left(split_part(btrim(name), ' ', 1), 100),
          last_name = CASE
            WHEN position(' ' in btrim(name)) = 0 THEN NULL
            ELSE nullif(
              left(btrim(substr(btrim(name), position(' ' in btrim(name)) + 1)), 100),
              ''
            )
          END
        WHERE name IS NOT NULL
          AND btrim(name) <> ''
          AND first_name IS NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
