from dataclasses import dataclass
from datetime import timedelta

from novoya_api.accounts.application.ports.mailer import AuthMailer
from novoya_api.accounts.application.ports.repositories import (
    OneTimeTokenRepository,
    PasswordCredentialRepository,
    UserRepository,
)
from novoya_api.accounts.application.ports.security import PasswordHasher, TokenGenerator
from novoya_api.accounts.application.services.one_time_tokens import issue_token
from novoya_api.accounts.domain.credentials import PasswordCredential
from novoya_api.accounts.domain.errors import EmailAlreadyUsed
from novoya_api.accounts.domain.one_time_token import TokenPurpose
from novoya_api.accounts.domain.policies import PasswordPolicy
from novoya_api.accounts.domain.user import User
from novoya_api.accounts.domain.value_objects import Email, PlainPassword
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.application.unit_of_work import UnitOfWork
from novoya_api.shared.domain.value_objects import Locale


@dataclass(frozen=True, slots=True)
class RegisterCommand:
    email: str
    password: str
    first_name: str
    last_name: str
    locale_hint: str | None  # the locale picked in the form, or the Accept-Language header
    ip_address: str | None


class Register:
    """Create a client account with a password and send the email verification link."""

    def __init__(
        self,
        users: UserRepository,
        credentials: PasswordCredentialRepository,
        tokens: OneTimeTokenRepository,
        hasher: PasswordHasher,
        token_generator: TokenGenerator,
        mailer: AuthMailer,
        rate_limiter: RateLimiter,
        uow: UnitOfWork,
        clock: Clock,
        policy: PasswordPolicy,
    ) -> None:
        self._users = users
        self._credentials = credentials
        self._tokens = tokens
        self._hasher = hasher
        self._token_generator = token_generator
        self._mailer = mailer
        self._rate_limiter = rate_limiter
        self._uow = uow
        self._clock = clock
        self._policy = policy

    async def __call__(self, cmd: RegisterCommand) -> User:
        await self._rate_limiter.hit(f"register:ip:{cmd.ip_address}", 10, timedelta(hours=1))
        email, password = Email(cmd.email), PlainPassword(cmd.password)
        self._policy.validate(password, email)
        # Telling that the email is taken is accepted: the information is not sensitive and
        # the message is clearer for the user. The rate limit stops mass checks.
        if await self._users.get_by_email(email) is not None:
            raise EmailAlreadyUsed("this email address already has an account")

        now = self._clock.now()
        user = User.register(
            email, cmd.first_name, cmd.last_name, Locale.from_hint(cmd.locale_hint), now
        )
        await self._users.add(user)
        password_hash = await self._hasher.hash(password)
        await self._credentials.upsert(PasswordCredential(user.id, password_hash, now))
        raw = await issue_token(
            self._tokens, self._token_generator, user.id, TokenPurpose.EMAIL_VERIFICATION, now
        )
        await self._uow.commit()

        # After the commit: never send a link to a token that does not exist.
        await self._mailer.send_email_verification(user.email, user.locale, raw)
        return user
