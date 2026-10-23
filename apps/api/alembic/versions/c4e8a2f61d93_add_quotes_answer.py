"""add quotes answer

Revision ID: c4e8a2f61d93
Revises: 0b6e3d9a5c71
Create Date: 2026-10-22 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e8a2f61d93"
down_revision: str | Sequence[str] | None = "0b6e3d9a5c71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("quotes", sa.Column("answer", sa.String(length=8), nullable=True))
    op.create_check_constraint(
        "ck_quotes_answer", "quotes", "answer IS NULL OR answer IN ('accepted', 'rejected')"
    )
    op.create_check_constraint(
        "ck_quotes_answer_decided_at", "quotes", "(answer IS NULL) = (decided_at IS NULL)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_quotes_answer_decided_at", "quotes", type_="check")
    op.drop_constraint("ck_quotes_answer", "quotes", type_="check")
    op.drop_column("quotes", "answer")
