from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from novoya_api.accounts.domain.actor import AdminActor, RoleActor
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import UserId

ADMIN_API = "admin_api"
CMD_GRANT_ROLE = "cmd_grant_role"


@dataclass(frozen=True, slots=True)
class RoleChange:
    """One line of the role change log. Never modified."""

    id: UUID
    user_id: UserId
    old_role: Role
    new_role: Role
    source: str  # ADMIN_API or CMD_GRANT_ROLE
    changed_by: UserId | None  # the admin; None for the command, or once that admin is deleted
    changed_at: datetime

    @classmethod
    def record(
        cls,
        user_id: UserId,
        old_role: Role,
        new_role: Role,
        by: RoleActor,
        now: datetime,
    ) -> "RoleChange":
        if isinstance(by, AdminActor):
            return cls(uuid4(), user_id, old_role, new_role, ADMIN_API, by.user_id, now)
        return cls(uuid4(), user_id, old_role, new_role, CMD_GRANT_ROLE, None, now)
