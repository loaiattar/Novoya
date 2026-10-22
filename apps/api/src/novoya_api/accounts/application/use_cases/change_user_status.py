from dataclasses import dataclass

from novoya_api.accounts.application.ports.repositories import SessionRepository, UserRepository
from novoya_api.accounts.domain.errors import UserNotFound
from novoya_api.accounts.domain.user import User, UserStatus
from novoya_api.accounts.domain.value_objects import UserId
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class ChangeUserStatusCommand:
    target: UserId
    new_status: UserStatus
    changed_by: UserId  # the signed-in admin


class ChangeUserStatus:
    """Disable or enable a user's account, and remember who did it and when.

    It does not check that the caller is an admin: the route does (require_admin).
    Both changes close every session of the user: the session check already refuses a
    disabled account, but without this an enabled account again would find its old sessions.
    Closing them again on enable also catches a sign-in that raced the disable.
    """

    def __init__(
        self,
        users: UserRepository,
        sessions: SessionRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._uow = uow
        self._clock = clock

    async def __call__(self, cmd: ChangeUserStatusCommand) -> User:
        target = await self._users.get(cmd.target)
        if target is None:
            raise UserNotFound("no user found")

        now = self._clock.now()
        if target.change_status(cmd.new_status, changed_by=cmd.changed_by, now=now):
            await self._users.save(target)
            await self._sessions.revoke_all_for_user(target.id, now)
            await self._uow.commit()
        return target
