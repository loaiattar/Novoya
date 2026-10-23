from novoya_api.accounts.application.ports.repositories import (
    OneTimeTokenRepository,
    UserRepository,
)
from novoya_api.accounts.application.ports.security import TokenGenerator
from novoya_api.accounts.application.services.one_time_tokens import consume_token
from novoya_api.accounts.domain.errors import InvalidOrExpiredToken
from novoya_api.accounts.domain.one_time_token import TokenPurpose
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork


class VerifyEmail:
    """Mark the email as verified with the token from the verification link."""

    def __init__(
        self,
        users: UserRepository,
        tokens: OneTimeTokenRepository,
        token_generator: TokenGenerator,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._users = users
        self._tokens = tokens
        self._token_generator = token_generator
        self._uow = uow
        self._clock = clock

    async def __call__(self, token: str) -> None:
        now = self._clock.now()
        stored = await consume_token(
            self._tokens, self._token_generator, token, TokenPurpose.EMAIL_VERIFICATION, now
        )
        user = await self._users.get(stored.user_id)
        if user is None:
            raise InvalidOrExpiredToken("this link is invalid or has expired")
        user.verify_email(now)
        await self._users.save(user)
        await self._uow.commit()
