from datetime import timedelta

from novoya_api.accounts.application.ports.mailer import AuthMailer
from novoya_api.accounts.application.ports.repositories import (
    OneTimeTokenRepository,
    PasswordCredentialRepository,
    SessionRepository,
    UserRepository,
)
from novoya_api.accounts.application.ports.security import PasswordHasher, TokenGenerator
from novoya_api.accounts.application.services.one_time_tokens import consume_token, issue_token
from novoya_api.accounts.domain.credentials import PasswordCredential
from novoya_api.accounts.domain.errors import InvalidOrExpiredToken
from novoya_api.accounts.domain.one_time_token import TokenPurpose
from novoya_api.accounts.domain.policies import PasswordPolicy
from novoya_api.accounts.domain.value_objects import Email, PlainPassword
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.application.unit_of_work import UnitOfWork


class RequestPasswordReset:
    """Send a reset link. Says nothing about whether the account exists."""

    def __init__(
        self,
        users: UserRepository,
        tokens: OneTimeTokenRepository,
        token_generator: TokenGenerator,
        mailer: AuthMailer,
        rate_limiter: RateLimiter,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._users = users
        self._tokens = tokens
        self._token_generator = token_generator
        self._mailer = mailer
        self._rate_limiter = rate_limiter
        self._uow = uow
        self._clock = clock

    async def __call__(self, email: str) -> None:
        address = Email(email)
        await self._rate_limiter.hit(f"reset:email:{address}", 3, timedelta(hours=1))
        user = await self._users.get_by_email(address)
        if user is None or not user.is_active:
            return
        now = self._clock.now()
        raw = await issue_token(
            self._tokens, self._token_generator, user.id, TokenPurpose.PASSWORD_RESET, now
        )
        await self._uow.commit()
        await self._mailer.send_password_reset(user.email, user.locale, raw)


class ResetPassword:
    """Set a new password with the token from the reset link, and close every session.

    It also proves the email address: the link was opened from that mailbox.
    """

    def __init__(
        self,
        users: UserRepository,
        credentials: PasswordCredentialRepository,
        sessions: SessionRepository,
        tokens: OneTimeTokenRepository,
        token_generator: TokenGenerator,
        hasher: PasswordHasher,
        mailer: AuthMailer,
        uow: UnitOfWork,
        clock: Clock,
        policy: PasswordPolicy,
    ) -> None:
        self._users = users
        self._credentials = credentials
        self._sessions = sessions
        self._tokens = tokens
        self._token_generator = token_generator
        self._hasher = hasher
        self._mailer = mailer
        self._uow = uow
        self._clock = clock
        self._policy = policy

    async def __call__(self, token: str, new_password: str) -> None:
        stored = await self._tokens.get(
            self._token_generator.hash(token), TokenPurpose.PASSWORD_RESET
        )
        user = await self._users.get(stored.user_id) if stored else None
        # A link sent before the account was disabled must not set a password.
        if user is None or not user.is_active:
            raise InvalidOrExpiredToken("this link is invalid or has expired")
        password = PlainPassword(new_password)
        self._policy.validate(password, user.email)  # before using the token: a typo keeps it

        now = self._clock.now()
        await consume_token(
            self._tokens, self._token_generator, token, TokenPurpose.PASSWORD_RESET, now
        )
        password_hash = await self._hasher.hash(password)
        credential = await self._credentials.get(user.id)
        if credential is None:
            credential = PasswordCredential(user.id, password_hash, now)
        else:
            credential.replace(password_hash, now)
        await self._credentials.upsert(credential)
        user.verify_email(now)
        await self._users.save(user)
        await self._sessions.revoke_all_for_user(user.id, now)
        await self._uow.commit()
        await self._mailer.send_password_changed_notice(user.email, user.locale)
