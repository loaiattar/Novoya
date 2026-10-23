"""add hidden and confirmed

The agents' hidden switch on partners, offers and extras, which the import never writes
(ADR 0014), and the agent's confirmation of a supplement whose amount depends on the group.

#120 was merged with these columns added inside d4f2a8c61e93 and e8b13c5d7a40, which had
already been run by some databases in their first version. Those databases are at head
without the columns; this migration adds them only where they are missing. Downgrading
d4f2a8c61e93 and e8b13c5d7a40 drops them, so the downgrade here does nothing.

Revision ID: a3c7e5f91b26
Revises: e8b13c5d7a40
Create Date: 2026-10-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3c7e5f91b26"
down_revision: str | Sequence[str] | None = "e8b13c5d7a40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


COLUMNS = [
    ("partners", "hidden"),
    ("offers", "hidden"),
    ("extras", "hidden"),
    ("plan_extras", "confirmed"),
]


def upgrade() -> None:
    for table, column in COLUMNS:
        op.execute(
            sa.text(
                f"ALTER TABLE {table} "
                f"ADD COLUMN IF NOT EXISTS {column} BOOLEAN NOT NULL DEFAULT false"
            )
        )


def downgrade() -> None:
    pass
