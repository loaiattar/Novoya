from datetime import timedelta

from novoya_api.accounts.application.ports.mailer import AuthMailer
from novoya_api.accounts.application.ports.repositories import (
    OneTimeTokenRepository,
    UserRepository,
)
from novoya_api.accounts.application.ports.security import TokenGenerator
from novoya_api.accounts.application.services.one_time_tokens import issue_token
from novoya_api.accounts.domain.one_time_token import TokenPurpose
from novoya_api.accounts.domain.value_objects import Email
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.application.unit_of_work import UnitOfWork


class ResendVerificationEmail:
    """Send a new verification link. Says nothing about whether the account exists."""

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
        await self._rate_limiter.hit(f"verify:email:{address}", 3, timedelta(hours=1))
        user = await self._users.get_by_email(address)
        if user is None or user.is_email_verified:
            return
        now = self._clock.now()
        raw = await issue_token(
            self._tokens, self._token_generator, user.id, TokenPurpose.EMAIL_VERIFICATION, now
        )
        await self._uow.commit()
        await self._mailer.send_email_verification(user.email, user.locale, raw)
