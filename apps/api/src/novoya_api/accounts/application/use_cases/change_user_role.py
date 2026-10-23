from dataclasses import dataclass

from novoya_api.accounts.application.ports.repositories import (
    RoleChangeRepository,
    UserRepository,
)
from novoya_api.accounts.domain.actor import RoleActor
from novoya_api.accounts.domain.errors import LastSuperAdminRequired, UserNotFound
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import User
from novoya_api.accounts.domain.value_objects import Email, UserId
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class ChangeUserRoleCommand:
    target: UserId | Email  # the admin API uses the id, the grant-role command the email
    new_role: Role
    by: RoleActor  # the signed-in admin, or GRANT_ROLE_COMMAND


class ChangeUserRole:
    """Give a user another role and log it.

    The route checks that the caller is an admin (require_admin), and the grant-role command
    needs access to the server. The entity checks the caller again (see User.change_role).
    """

    def __init__(
        self,
        users: UserRepository,
        role_changes: RoleChangeRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._users = users
        self._role_changes = role_changes
        self._uow = uow
        self._clock = clock

    async def __call__(self, cmd: ChangeUserRoleCommand) -> User:
        if isinstance(cmd.target, Email):
            target = await self._users.get_by_email(cmd.target)
        else:
            target = await self._users.get(cmd.target)
        if target is None:
            raise UserNotFound("no user found")

        # A disabled super admin cannot act on admins: it does not count as the last one.
        was_active_super_admin = target.role is Role.SUPER_ADMIN and target.is_active
        # The entity's rules first (not your own role, who may touch admins, verified email);
        # nothing is saved yet.
        change = target.change_role(cmd.new_role, by=cmd.by, now=self._clock.now())
        if (
            was_active_super_admin
            and cmd.new_role is not Role.SUPER_ADMIN
            and await self._users.count_active_with_role(Role.SUPER_ADMIN) <= 1
        ):
            raise LastSuperAdminRequired("name another super admin first")

        if change is not None:
            await self._users.save(target)
            await self._role_changes.add(change)
            await self._uow.commit()
        return target
