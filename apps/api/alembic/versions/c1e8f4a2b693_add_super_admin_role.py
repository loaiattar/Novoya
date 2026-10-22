"""add the super_admin role

Revision ID: c1e8f4a2b693
Revises: 0b6e3d9a5c71
Create Date: 2026-10-22 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1e8f4a2b693"
down_revision: str | Sequence[str] | None = "0b6e3d9a5c71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_ROLES = "('client', 'agent', 'admin')"
_NEW_ROLES = "('client', 'agent', 'admin', 'super_admin')"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", f"role IN {_NEW_ROLES}")
    op.create_check_constraint(
        "ck_role_changes_old_role", "role_changes", f"old_role IN {_NEW_ROLES}"
    )
    op.create_check_constraint(
        "ck_role_changes_new_role", "role_changes", f"new_role IN {_NEW_ROLES}"
    )


def downgrade() -> None:
    """Downgrade schema. Refused while a super admin exists: their role would have no value."""
    count = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM users WHERE role = 'super_admin'"))
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            f"{count} user(s) have the super_admin role: give them another role first"
        )
    op.drop_constraint("ck_role_changes_new_role", "role_changes", type_="check")
    op.drop_constraint("ck_role_changes_old_role", "role_changes", type_="check")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", f"role IN {_OLD_ROLES}")
