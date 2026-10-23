"""add messages (advisor chat, #169)

Revision ID: a9d3f1c7e524
Revises: f2b8d4c6a917
Create Date: 2026-10-23 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9d3f1c7e524"
down_revision: str | Sequence[str] | None = "f2b8d4c6a917"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wish_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("from_agency", sa.Boolean(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wish_id"], ["wishes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_wish_id_sent_at", "messages", ["wish_id", "sent_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_messages_wish_id_sent_at", table_name="messages")
    op.drop_table("messages")
