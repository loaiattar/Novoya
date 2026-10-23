from datetime import timedelta

from novoya_api.accounts.application.dto import CurrentUserView
from novoya_api.accounts.application.ports.mailer import AuthMailer
from novoya_api.accounts.application.ports.repositories import (
    PasswordCredentialRepository,
    SessionRepository,
)
from novoya_api.accounts.application.ports.security import PasswordHasher
from novoya_api.accounts.domain.errors import InvalidCredentials, NoPasswordSet
from novoya_api.accounts.domain.policies import PasswordPolicy
from novoya_api.accounts.domain.value_objects import PlainPassword
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.application.unit_of_work import UnitOfWork


class ChangePassword:
    """Change the password of the signed-in user and close their other sessions."""

    def __init__(
        self,
        credentials: PasswordCredentialRepository,
        sessions: SessionRepository,
        hasher: PasswordHasher,
        mailer: AuthMailer,
        rate_limiter: RateLimiter,
        uow: UnitOfWork,
        clock: Clock,
        policy: PasswordPolicy,
    ) -> None:
        self._credentials = credentials
        self._sessions = sessions
        self._hasher = hasher
        self._mailer = mailer
        self._rate_limiter = rate_limiter
        self._uow = uow
        self._clock = clock
        self._policy = policy

    async def __call__(
        self, user: CurrentUserView, current_password: str, new_password: str
    ) -> None:
        await self._rate_limiter.hit(f"password_change:{user.user_id}", 10, timedelta(minutes=15))
        credential = await self._credentials.get(user.user_id)
        if credential is None:
            raise NoPasswordSet("this account has no password; use the forgotten password link")
        if not await self._hasher.verify(credential.password_hash, PlainPassword(current_password)):
            raise InvalidCredentials("the current password is wrong")
        password = PlainPassword(new_password)
        self._policy.validate(password, user.email)

        now = self._clock.now()
        credential.replace(await self._hasher.hash(password), now)
        await self._credentials.upsert(credential)
        await self._sessions.revoke_all_for_user(
            user.user_id, now, except_session_id=user.session_id
        )
        await self._uow.commit()
        await self._mailer.send_password_changed_notice(user.email, user.locale)
