from dataclasses import dataclass

from novoya_api.accounts.application.ports.repositories import (
    RoleChangeRepository,
    UserRepository,
)
from novoya_api.accounts.domain.errors import LastAdminRequired, UserNotFound
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import User
from novoya_api.accounts.domain.value_objects import Email, UserId
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class ChangeUserRoleCommand:
    target: UserId | Email  # the admin API uses the id, the grant-role command the email
    new_role: Role
    changed_by: UserId | None  # the signed-in admin, or None for the grant-role command


class ChangeUserRole:
    """Give a user another role and log it.

    It does not check that the caller is an admin: the route does (require_admin), and the
    grant-role command needs access to the server. The business rules apply to both.
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

        # A disabled admin cannot manage roles: it does not count as the last one.
        was_active_admin = target.role is Role.ADMIN and target.is_active
        # The entity's rules first (not your own role, verified email); nothing is saved yet.
        change = target.change_role(cmd.new_role, changed_by=cmd.changed_by, now=self._clock.now())
        if (
            was_active_admin
            and cmd.new_role is not Role.ADMIN
            and await self._users.count_active_with_role(Role.ADMIN) <= 1
        ):
            raise LastAdminRequired("name another admin first")

        if change is not None:
            await self._users.save(target)
            await self._role_changes.add(change)
            await self._uow.commit()
        return target
