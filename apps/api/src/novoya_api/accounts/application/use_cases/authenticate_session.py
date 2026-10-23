from novoya_api.accounts.application.dto import CurrentUserView
from novoya_api.accounts.application.ports.repositories import SessionRepository
from novoya_api.accounts.application.ports.security import TokenGenerator
from novoya_api.accounts.application.services.session_opener import SessionPolicy
from novoya_api.accounts.domain.errors import SessionInvalid
from novoya_api.accounts.domain.value_objects import SessionToken
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork


class AuthenticateSession:
    """Find who sends the request, from the session cookie. Runs on every protected request.

    The role is read from the database each time, so a role change applies to the next request.
    """

    def __init__(
        self,
        sessions: SessionRepository,
        tokens: TokenGenerator,
        uow: UnitOfWork,
        clock: Clock,
        policy: SessionPolicy,
    ) -> None:
        self._sessions = sessions
        self._tokens = tokens
        self._uow = uow
        self._clock = clock
        self._policy = policy

    async def __call__(self, token: SessionToken) -> CurrentUserView:
        found = await self._sessions.get_with_user(self._tokens.hash(token.value))
        if found is None:
            raise SessionInvalid("not signed in")
        session, user = found
        now = self._clock.now()
        if not session.is_active(now) or not user.is_active:
            raise SessionInvalid("the session has expired")
        if session.touch(now, self._policy.idle_ttl):
            await self._sessions.save(session)
            await self._uow.commit()
        return CurrentUserView.of(user, session.id)
