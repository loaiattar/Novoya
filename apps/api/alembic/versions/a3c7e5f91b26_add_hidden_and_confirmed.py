"""add hidden and confirmed

The agents' hidden switch on partners, offers and extras, which the import never writes
(ADR 0014), and the agent's confirmation of a supplement whose amount depends on the group.

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


def upgrade() -> None:
    for table in ("partners", "offers", "extras"):
        op.add_column(
            table, sa.Column("hidden", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
    op.add_column(
        "plan_extras",
        sa.Column("confirmed", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("plan_extras", "confirmed")
    for table in ("extras", "offers", "partners"):
        op.drop_column(table, "hidden")
