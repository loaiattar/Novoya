"""In-memory implementations of the accounts ports. No database, no SMTP, no Argon2."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from novoya_api.accounts.application.ports.identity_provider import (
    AuthorizationRequest,
    PendingSignIn,
)
from novoya_api.accounts.domain.auth_session import AuthSession
from novoya_api.accounts.domain.credentials import PasswordCredential
from novoya_api.accounts.domain.errors import EmailAlreadyUsed, IdentityAlreadyLinked
from novoya_api.accounts.domain.oauth_identity import ExternalIdentity, OAuthIdentity
from novoya_api.accounts.domain.one_time_token import OneTimeToken, TokenPurpose
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.role_change import RoleChange
from novoya_api.accounts.domain.user import User, UserStatus
from novoya_api.accounts.domain.value_objects import Email, PasswordHash, PlainPassword, UserId
from novoya_api.shared.domain.value_objects import Locale


class FrozenClock:
    def __init__(self, now: datetime | None = None) -> None:
        self.current = now or datetime(2026, 10, 19, 9, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


# Entities are copied in and out, like a database would: a use case must call save().


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.rows: dict[UserId, User] = {}

    async def get(self, user_id: UserId) -> User | None:
        user = self.rows.get(user_id)
        return replace(user) if user else None

    async def get_by_email(self, email: Email) -> User | None:
        return next((replace(u) for u in self.rows.values() if u.email == email), None)

    async def add(self, user: User) -> None:
        if any(u.email == user.email for u in self.rows.values()):
            raise EmailAlreadyUsed("this email address already has an account")
        self.rows[user.id] = replace(user)

    async def save(self, user: User) -> None:
        self.rows[user.id] = replace(user)

    async def delete(self, user_id: UserId) -> None:
        self.rows.pop(user_id, None)

    async def count_active_with_role(self, role: Role) -> int:
        return sum(1 for u in self.rows.values() if u.role is role and u.is_active)

    async def search(
        self, query: str | None, role: Role | None, limit: int, offset: int
    ) -> list[User]:
        users = sorted(self.rows.values(), key=lambda u: u.created_at, reverse=True)
        if query:
            q = query.lower()
            users = [
                u
                for u in users
                if q in u.email.value
                or q in (u.name or "").lower()
                or q in (u.first_name or "").lower()
                or q in (u.last_name or "").lower()
            ]
        if role is not None:
            users = [u for u in users if u.role is role]
        return [replace(u) for u in users[offset : offset + limit]]


class InMemoryRoleChangeRepository:
    def __init__(self) -> None:
        self.rows: list[RoleChange] = []

    async def add(self, change: RoleChange) -> None:
        self.rows.append(change)


class InMemoryPasswordCredentialRepository:
    def __init__(self) -> None:
        self.rows: dict[UserId, PasswordCredential] = {}

    async def get(self, user_id: UserId) -> PasswordCredential | None:
        credential = self.rows.get(user_id)
        return replace(credential) if credential else None

    async def upsert(self, credential: PasswordCredential) -> None:
        self.rows[credential.user_id] = replace(credential)

    async def delete(self, user_id: UserId) -> None:
        self.rows.pop(user_id, None)


class InMemoryOAuthIdentityRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], OAuthIdentity] = {}

    async def get(self, provider: str, subject: str) -> OAuthIdentity | None:
        identity = self.rows.get((provider, subject))
        return replace(identity) if identity else None

    async def add(self, identity: OAuthIdentity) -> None:
        if (identity.provider, identity.subject) in self.rows:
            raise IdentityAlreadyLinked("this account is already linked to another user")
        self.rows[(identity.provider, identity.subject)] = replace(identity)

    async def save(self, identity: OAuthIdentity) -> None:
        self.rows[(identity.provider, identity.subject)] = replace(identity)

    async def providers_for_user(self, user_id: UserId) -> set[str]:
        return {i.provider for i in self.rows.values() if i.user_id == user_id}


class InMemoryOAuthStateStore:
    def __init__(self) -> None:
        self.rows: dict[str, tuple[PendingSignIn, datetime]] = {}

    async def put(
        self, state_hash: str, pending: PendingSignIn, expires_at: datetime, now: datetime
    ) -> None:
        self.rows[state_hash] = (pending, expires_at)

    async def pop(self, state_hash: str, now: datetime) -> PendingSignIn | None:
        row = self.rows.pop(state_hash, None)
        if row is None or row[1] <= now:
            return None
        return row[0]


class InMemorySessionRepository:
    def __init__(self, users: InMemoryUserRepository) -> None:
        self.rows: dict[UUID, AuthSession] = {}
        self._users = users

    async def get(self, token_hash: str) -> AuthSession | None:
        return next((replace(s) for s in self.rows.values() if s.token_hash == token_hash), None)

    async def get_with_user(self, token_hash: str) -> tuple[AuthSession, User] | None:
        session = await self.get(token_hash)
        if session is None:
            return None
        user = await self._users.get(session.user_id)
        return (session, user) if user else None

    async def add(self, session: AuthSession) -> None:
        self.rows[session.id] = replace(session)

    async def save(self, session: AuthSession) -> None:
        self.rows[session.id] = replace(session)

    async def revoke_all_for_user(
        self, user_id: UserId, now: datetime, except_session_id: UUID | None = None
    ) -> None:
        for session in self.rows.values():
            if session.user_id == user_id and session.id != except_session_id:
                session.revoke(now)

    async def delete_expired(self, now: datetime) -> None:
        self.rows = {
            key: session for key, session in self.rows.items() if session.absolute_expires_at > now
        }


class InMemoryOneTimeTokenRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, OneTimeToken] = {}

    async def get(self, token_hash: str, purpose: TokenPurpose) -> OneTimeToken | None:
        return next(
            (
                replace(t)
                for t in self.rows.values()
                if t.token_hash == token_hash and t.purpose is purpose
            ),
            None,
        )

    async def add(self, token: OneTimeToken) -> None:
        self.rows[token.id] = replace(token)

    async def save(self, token: OneTimeToken) -> None:
        self.rows[token.id] = replace(token)

    async def invalidate_all(self, user_id: UserId, purpose: TokenPurpose, now: datetime) -> None:
        for token in self.rows.values():
            if token.user_id == user_id and token.purpose is purpose and token.used_at is None:
                token.used_at = now

    async def delete_expired(self, now: datetime) -> None:
        self.rows = {key: token for key, token in self.rows.items() if token.expires_at > now}


@dataclass
class InMemoryStore:
    """Same shape as AccountsStore in the composition root."""

    users: InMemoryUserRepository = field(default_factory=InMemoryUserRepository)
    credentials: InMemoryPasswordCredentialRepository = field(
        default_factory=InMemoryPasswordCredentialRepository
    )
    tokens: InMemoryOneTimeTokenRepository = field(default_factory=InMemoryOneTimeTokenRepository)
    role_changes: InMemoryRoleChangeRepository = field(default_factory=InMemoryRoleChangeRepository)
    identities: InMemoryOAuthIdentityRepository = field(
        default_factory=InMemoryOAuthIdentityRepository
    )
    oauth_states: InMemoryOAuthStateStore = field(default_factory=InMemoryOAuthStateStore)
    uow: FakeUnitOfWork = field(default_factory=FakeUnitOfWork)
    sessions: InMemorySessionRepository = field(init=False)

    def __post_init__(self) -> None:
        self.sessions = InMemorySessionRepository(self.users)


class PlainTextPasswordHasher:
    """Fast stand-in for Argon2."""

    async def hash(self, password: PlainPassword) -> PasswordHash:
        return PasswordHash(f"hashed:{password.value}")

    async def verify(self, hashed: PasswordHash, password: PlainPassword) -> bool:
        return hashed.value == f"hashed:{password.value}"

    def needs_rehash(self, hashed: PasswordHash) -> bool:
        return False


class SequentialTokenGenerator:
    def __init__(self) -> None:
        self.count = 0

    def generate(self) -> str:
        self.count += 1
        return f"token-{self.count}"

    def hash(self, token: str) -> str:
        return f"sha:{token}"


@dataclass
class SentEmail:
    kind: str
    to: str
    locale: Locale
    token: str | None


class RecordingMailer:
    def __init__(self) -> None:
        self.sent: list[SentEmail] = []

    async def send_email_verification(self, to: Email, locale: Locale, token: str) -> None:
        self.sent.append(SentEmail("email_verification", to.value, locale, token))

    async def send_password_reset(self, to: Email, locale: Locale, token: str) -> None:
        self.sent.append(SentEmail("password_reset", to.value, locale, token))

    async def send_password_changed_notice(self, to: Email, locale: Locale) -> None:
        self.sent.append(SentEmail("password_changed", to.value, locale, None))

    def last_token(self, to: str, kind: str) -> str:
        return next(m.token for m in reversed(self.sent) if m.to == to and m.kind == kind)


class NoopRateLimiter:
    async def hit(self, key: str, limit: int, window: timedelta) -> None:
        pass

    async def reset(self, key: str) -> None:
        pass


def make_user(
    email: str = "alice@example.com",
    role: Role = Role.CLIENT,
    verified: bool = True,
    status: UserStatus = UserStatus.ACTIVE,
    now: datetime | None = None,
) -> User:
    now = now or datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
    user = User.register(Email(email), "Alice", "Martin", Locale.EN, now)
    user.role = role
    user.status = status
    if verified:
        user.verify_email(now)
    return user


def google_identity(
    subject: str = "google-sub-1",
    email: str = "alice@example.com",
    email_verified: bool = True,
    name: str | None = "Alice Martin",
    first_name: str | None = "Alice",
    last_name: str | None = "Martin",
    locale: str | None = "en",
    email_authoritative: bool = True,
) -> ExternalIdentity:
    return ExternalIdentity(
        "google",
        subject,
        Email(email),
        email_verified,
        email_authoritative,
        name,
        first_name,
        last_name,
        locale,
    )


class FakeIdentityProvider:
    """Stands for Google: a fixed authorization URL, and the identity the test chose."""

    def __init__(self, identity: ExternalIdentity | None = None, name: str = "google") -> None:
        self.name = name
        self.identity = identity or google_identity()
        self.error: Exception | None = None
        self.requests = 0
        self.fetches: list[dict] = []

    def build_authorization_request(self, redirect_uri: str) -> AuthorizationRequest:
        self.requests += 1
        n = self.requests
        return AuthorizationRequest(
            url=f"https://idp.example/auth?state=state-{n}&redirect_uri={redirect_uri}",
            state=f"state-{n}",
            code_verifier=f"verifier-{n}",
            nonce=f"nonce-{n}",
        )

    async def fetch_identity(
        self, code: str, code_verifier: str, redirect_uri: str, nonce: str
    ) -> ExternalIdentity:
        self.fetches.append(
            {
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
                "nonce": nonce,
            }
        )
        if self.error is not None:
            raise self.error
        return self.identity


class RecordingDataEraser:
    """UserDataEraser that only remembers whose data it was asked to erase."""

    def __init__(self) -> None:
        self.erased: list[UserId] = []

    async def erase(self, user_id: UserId) -> None:
        self.erased.append(user_id)
