from dataclasses import dataclass
from datetime import timedelta

from novoya_api.accounts.application.dto import ClientInfo
from novoya_api.accounts.application.ports.repositories import SessionRepository
from novoya_api.accounts.application.ports.security import TokenGenerator
from novoya_api.accounts.domain.auth_session import AuthSession
from novoya_api.accounts.domain.user import User
from novoya_api.accounts.domain.value_objects import SessionToken
from novoya_api.shared.application.clock import Clock


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    idle_ttl: timedelta = timedelta(days=7)
    absolute_ttl: timedelta = timedelta(days=30)
    require_verified_email: bool = True


class SessionOpener:
    """What happens on EVERY successful sign-in, whatever the way (password, Google...)."""

    def __init__(
        self,
        sessions: SessionRepository,
        tokens: TokenGenerator,
        clock: Clock,
        policy: SessionPolicy,
    ) -> None:
        self._sessions = sessions
        self._tokens = tokens
        self._clock = clock
        self._policy = policy

    @property
    def policy(self) -> SessionPolicy:
        return self._policy

    async def open(self, user: User, client: ClientInfo) -> SessionToken:
        """Check the account may sign in and open a new session. The role is not touched."""
        user.ensure_can_sign_in(require_verified_email=self._policy.require_verified_email)
        if client.current_token is not None:
            await self.revoke(client.current_token)  # a new token on each sign-in: no fixation
        now = self._clock.now()
        # No worker cleans the table: each sign-in deletes the sessions past their 30 days.
        await self._sessions.delete_expired(now)
        raw = self._tokens.generate()
        session = AuthSession.open(
            user.id,
            self._tokens.hash(raw),
            now,
            self._policy.idle_ttl,
            self._policy.absolute_ttl,
            client.user_agent,
        )
        await self._sessions.add(session)
        return SessionToken(raw)

    async def revoke(self, token: SessionToken) -> None:
        session = await self._sessions.get(self._tokens.hash(token.value))
        if session is not None:
            session.revoke(self._clock.now())
            await self._sessions.save(session)
