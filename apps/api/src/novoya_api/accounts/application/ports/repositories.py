from datetime import datetime
from typing import Protocol
from uuid import UUID

from novoya_api.accounts.domain.auth_session import AuthSession
from novoya_api.accounts.domain.credentials import PasswordCredential
from novoya_api.accounts.domain.oauth_identity import OAuthIdentity
from novoya_api.accounts.domain.one_time_token import OneTimeToken, TokenPurpose
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.role_change import RoleChange
from novoya_api.accounts.domain.user import User
from novoya_api.accounts.domain.value_objects import Email, UserId


class UserRepository(Protocol):
    async def get(self, user_id: UserId) -> User | None: ...

    async def get_by_email(self, email: Email) -> User | None: ...

    async def add(self, user: User) -> None:
        """Raise EmailAlreadyUsed if the email is taken."""
        ...

    async def save(self, user: User) -> None: ...

    async def delete(self, user_id: UserId) -> None:
        """Erases the user. Sessions, sign-in methods and tokens go with it (cascade)."""
        ...

    async def count_active_with_role(self, role: Role) -> int: ...

    async def search(
        self, query: str | None, role: Role | None, limit: int, offset: int
    ) -> list[User]: ...


class RoleChangeRepository(Protocol):
    async def add(self, change: RoleChange) -> None: ...


class PasswordCredentialRepository(Protocol):
    async def get(self, user_id: UserId) -> PasswordCredential | None: ...

    async def upsert(self, credential: PasswordCredential) -> None: ...

    async def delete(self, user_id: UserId) -> None: ...


class OAuthIdentityRepository(Protocol):
    async def get(self, provider: str, subject: str) -> OAuthIdentity | None: ...

    async def add(self, identity: OAuthIdentity) -> None:
        """Raise IdentityAlreadyLinked if this provider account is linked already."""
        ...

    async def save(self, identity: OAuthIdentity) -> None: ...

    async def providers_for_user(self, user_id: UserId) -> set[str]:
        """The providers linked to this user, e.g. {"google"}."""
        ...


class SessionRepository(Protocol):
    async def get(self, token_hash: str) -> AuthSession | None: ...

    async def get_with_user(self, token_hash: str) -> tuple[AuthSession, User] | None:
        """The session and its user in one query: the role is always the current one."""
        ...

    async def add(self, session: AuthSession) -> None: ...

    async def save(self, session: AuthSession) -> None: ...

    async def revoke_all_for_user(
        self, user_id: UserId, now: datetime, except_session_id: UUID | None = None
    ) -> None: ...


class OneTimeTokenRepository(Protocol):
    async def get(self, token_hash: str, purpose: TokenPurpose) -> OneTimeToken | None: ...

    async def add(self, token: OneTimeToken) -> None: ...

    async def save(self, token: OneTimeToken) -> None: ...

    async def invalidate_all(self, user_id: UserId, purpose: TokenPurpose, now: datetime) -> None:
        """Mark the user's unused tokens for this purpose as used."""
        ...
