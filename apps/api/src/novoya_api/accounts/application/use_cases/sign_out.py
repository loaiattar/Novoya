from novoya_api.accounts.application.ports.repositories import SessionRepository
from novoya_api.accounts.application.services.session_opener import SessionOpener
from novoya_api.accounts.domain.value_objects import SessionToken, UserId
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork


class SignOut:
    """Close the current session."""

    def __init__(self, opener: SessionOpener, uow: UnitOfWork) -> None:
        self._opener = opener
        self._uow = uow

    async def __call__(self, token: SessionToken) -> None:
        await self._opener.revoke(token)
        await self._uow.commit()


class SignOutEverywhere:
    """Close every session of the user, on every device."""

    def __init__(self, sessions: SessionRepository, uow: UnitOfWork, clock: Clock) -> None:
        self._sessions = sessions
        self._uow = uow
        self._clock = clock

    async def __call__(self, user_id: UserId) -> None:
        await self._sessions.revoke_all_for_user(user_id, self._clock.now())
        await self._uow.commit()
