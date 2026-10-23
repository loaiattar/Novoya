from dataclasses import dataclass
from datetime import timedelta

from novoya_api.accounts.application.dto import ClientInfo
from novoya_api.accounts.application.ports.repositories import (
    PasswordCredentialRepository,
    UserRepository,
)
from novoya_api.accounts.application.ports.security import PasswordHasher
from novoya_api.accounts.application.services.session_opener import SessionOpener
from novoya_api.accounts.domain.errors import InvalidCredentials
from novoya_api.accounts.domain.value_objects import (
    Email,
    PasswordHash,
    PlainPassword,
    SessionToken,
)
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.application.unit_of_work import UnitOfWork

WINDOW = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class SignInWithPasswordCommand:
    email: str
    password: str
    client: ClientInfo


class SignInWithPassword:
    def __init__(
        self,
        users: UserRepository,
        credentials: PasswordCredentialRepository,
        hasher: PasswordHasher,
        opener: SessionOpener,
        rate_limiter: RateLimiter,
        uow: UnitOfWork,
        clock: Clock,
        dummy_hash: PasswordHash,
    ) -> None:
        self._users = users
        self._credentials = credentials
        self._hasher = hasher
        self._opener = opener
        self._rate_limiter = rate_limiter
        self._uow = uow
        self._clock = clock
        self._dummy_hash = dummy_hash

    async def __call__(self, cmd: SignInWithPasswordCommand) -> SessionToken:
        email, password = Email(cmd.email), PlainPassword(cmd.password)
        # Per IP first, then per email *and* IP: a limit on the email alone would let anyone
        # lock the owner out by failing on purpose (plan §12.2).
        await self._rate_limiter.hit(f"login:ip:{cmd.client.ip_address}", 50, WINDOW)
        await self._rate_limiter.hit(f"login:{email}:{cmd.client.ip_address}", 10, WINDOW)

        user = await self._users.get_by_email(email)
        credential = await self._credentials.get(user.id) if user else None
        if user is None or credential is None:
            # Same work as for a real account: the response time does not tell it exists.
            await self._hasher.verify(self._dummy_hash, password)
            raise InvalidCredentials("wrong email or password")
        if not await self._hasher.verify(credential.password_hash, password):
            raise InvalidCredentials("wrong email or password")

        if self._hasher.needs_rehash(credential.password_hash):
            credential.replace(await self._hasher.hash(password), self._clock.now())
            await self._credentials.upsert(credential)

        token = await self._opener.open(user, cmd.client)
        await self._uow.commit()
        await self._rate_limiter.reset(f"login:{email}:{cmd.client.ip_address}")
        return token
