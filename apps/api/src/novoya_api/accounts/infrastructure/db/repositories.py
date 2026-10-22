"""Repositories of the accounts module, with SQLAlchemy.

They map rows to entities and back: no ORM object leaves this file. They never commit; the
use case does, through the UnitOfWork that shares their session.
"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.application.ports.identity_provider import PendingSignIn
from novoya_api.accounts.domain.auth_session import AuthSession
from novoya_api.accounts.domain.credentials import PasswordCredential
from novoya_api.accounts.domain.errors import EmailAlreadyUsed, IdentityAlreadyLinked
from novoya_api.accounts.domain.oauth_identity import OAuthIdentity
from novoya_api.accounts.domain.one_time_token import OneTimeToken, TokenPurpose
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.role_change import RoleChange
from novoya_api.accounts.domain.user import User, UserStatus
from novoya_api.accounts.domain.value_objects import Email, PasswordHash, UserId
from novoya_api.accounts.infrastructure.db.models import (
    OAuthIdentityModel,
    OAuthStateModel,
    OneTimeTokenModel,
    PasswordCredentialModel,
    RoleChangeModel,
    SessionModel,
    UserModel,
)
from novoya_api.shared.domain.value_objects import Locale


def user_to_entity(row: UserModel) -> User:
    return User(
        id=UserId(row.id),
        email=Email(row.email),
        name=row.name,
        first_name=row.first_name,
        last_name=row.last_name,
        role=Role(row.role),
        locale=Locale(row.locale),
        status=UserStatus(row.status),
        email_verified_at=row.email_verified_at,
        created_at=row.created_at,
        status_changed_by=UserId(row.status_changed_by) if row.status_changed_by else None,
        status_changed_at=row.status_changed_at,
    )


def user_columns(user: User) -> dict[str, object]:
    return {
        "email": user.email.value,
        "name": user.name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role.value,
        "locale": user.locale.value,
        "status": user.status.value,
        "email_verified_at": user.email_verified_at,
        "status_changed_by": user.status_changed_by.value if user.status_changed_by else None,
        "status_changed_at": user.status_changed_at,
    }


class SqlUserRepository:
    """save() writes only the columns the use case changed since it read the user. Writing
    them all would undo what another request committed meanwhile: a sign-in that read an
    agent would give the role back after an admin's demotion."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._read: dict[UserId, dict[str, object]] = {}  # each user as this request read it

    def _entity(self, row: UserModel) -> User:
        user = user_to_entity(row)
        self._read[user.id] = user_columns(user)
        return user

    async def get(self, user_id: UserId) -> User | None:
        row = await self._session.get(UserModel, user_id.value)
        return self._entity(row) if row else None

    async def list_by_ids(self, user_ids: Sequence[UUID]) -> list[User]:
        if not user_ids:
            return []
        rows = await self._session.scalars(select(UserModel).where(UserModel.id.in_(user_ids)))
        return [self._entity(row) for row in rows]

    async def get_by_email(self, email: Email) -> User | None:
        row = await self._session.scalar(select(UserModel).where(UserModel.email == email.value))
        return self._entity(row) if row else None

    async def add(self, user: User) -> None:
        columns = user_columns(user)
        self._session.add(UserModel(id=user.id.value, created_at=user.created_at, **columns))
        try:
            await self._session.flush()  # two sign-ups at once: the unique index decides
        except IntegrityError as exc:
            raise EmailAlreadyUsed("this email address already has an account") from exc
        self._read[user.id] = columns

    async def delete(self, user_id: UserId) -> None:
        await self._session.execute(delete(UserModel).where(UserModel.id == user_id.value))
        self._read.pop(user_id, None)

    async def save(self, user: User) -> None:
        columns = user_columns(user)
        read = self._read.get(user.id)
        changed = {k: v for k, v in columns.items() if read is None or read[k] != v}
        if changed:
            await self._session.execute(
                update(UserModel).where(UserModel.id == user.id.value).values(**changed)
            )
        self._read[user.id] = columns

    async def count_by_role(self) -> dict[str, int]:
        """Every account, disabled ones too, by role. Roles with nobody are left out."""
        rows = await self._session.execute(
            select(UserModel.role, func.count()).group_by(UserModel.role)
        )
        return {role: count for role, count in rows}

    async def count_active_with_role(self, role: Role) -> int:
        # FOR UPDATE locks these rows until commit: two admins demoting each other at the
        # same time are counted one after the other, so the last admin is always kept.
        ids = await self._session.scalars(
            select(UserModel.id)
            .where(UserModel.role == role.value, UserModel.status == UserStatus.ACTIVE.value)
            .with_for_update()
        )
        return len(ids.all())

    async def search(
        self, query: str | None, role: Role | None, limit: int, offset: int
    ) -> list[User]:
        statement = select(UserModel)
        if query:
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    UserModel.email.ilike(pattern),
                    UserModel.name.ilike(pattern),
                    UserModel.first_name.ilike(pattern),
                    UserModel.last_name.ilike(pattern),
                )
            )
        if role is not None:
            statement = statement.where(UserModel.role == role.value)
        statement = statement.order_by(UserModel.created_at.desc()).limit(limit).offset(offset)
        rows = await self._session.scalars(statement)
        return [self._entity(row) for row in rows]


class SqlRoleChangeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, change: RoleChange) -> None:
        self._session.add(
            RoleChangeModel(
                id=change.id,
                user_id=change.user_id.value,
                old_role=change.old_role.value,
                new_role=change.new_role.value,
                source=change.source,
                changed_by=change.changed_by.value if change.changed_by else None,
                changed_at=change.changed_at,
            )
        )


class SqlPasswordCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UserId) -> PasswordCredential | None:
        row = await self._session.get(PasswordCredentialModel, user_id.value)
        if row is None:
            return None
        return PasswordCredential(
            UserId(row.user_id), PasswordHash(row.password_hash), row.updated_at
        )

    async def upsert(self, credential: PasswordCredential) -> None:
        row = await self._session.get(PasswordCredentialModel, credential.user_id.value)
        if row is None:
            row = PasswordCredentialModel(user_id=credential.user_id.value)
            self._session.add(row)
        row.password_hash = credential.password_hash.value
        row.updated_at = credential.updated_at

    async def delete(self, user_id: UserId) -> None:
        await self._session.execute(
            delete(PasswordCredentialModel).where(PasswordCredentialModel.user_id == user_id.value)
        )


IDENTITY_UNIQUE = ("uq_oauth_identities_provider_subject", "uq_oauth_identities_user_provider")


def identity_to_entity(row: OAuthIdentityModel) -> OAuthIdentity:
    return OAuthIdentity(
        id=row.id,
        user_id=UserId(row.user_id),
        provider=row.provider,
        subject=row.subject,
        created_at=row.created_at,
        last_login_at=row.last_login_at,
    )


class SqlOAuthIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, provider: str, subject: str) -> OAuthIdentity | None:
        row = await self._session.scalar(
            select(OAuthIdentityModel).where(
                OAuthIdentityModel.provider == provider, OAuthIdentityModel.subject == subject
            )
        )
        return identity_to_entity(row) if row else None

    async def add(self, identity: OAuthIdentity) -> None:
        self._session.add(
            OAuthIdentityModel(
                id=identity.id,
                user_id=identity.user_id.value,
                provider=identity.provider,
                subject=identity.subject,
                created_at=identity.created_at,
                last_login_at=identity.last_login_at,
            )
        )
        try:
            await self._session.flush()  # two first sign-ins at once: the unique index decides
        except IntegrityError as exc:
            # Only these indexes mean "already linked"; any other violation is a bug to surface.
            if not any(name in str(exc.orig) for name in IDENTITY_UNIQUE):
                raise
            raise IdentityAlreadyLinked("this account is already linked to another user") from exc

    async def save(self, identity: OAuthIdentity) -> None:
        row = await self._session.get(OAuthIdentityModel, identity.id)
        if row is not None:
            row.last_login_at = identity.last_login_at

    async def providers_for_user(self, user_id: UserId) -> set[str]:
        rows = await self._session.scalars(
            select(OAuthIdentityModel.provider).where(OAuthIdentityModel.user_id == user_id.value)
        )
        return set(rows)


class SqlOAuthStateStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def put(
        self, state_hash: str, pending: PendingSignIn, expires_at: datetime, now: datetime
    ) -> None:
        # No worker cleans the table: each new sign-in removes the expired ones.
        await self._session.execute(
            delete(OAuthStateModel).where(OAuthStateModel.expires_at <= now)
        )
        self._session.add(
            OAuthStateModel(
                state_hash=state_hash,
                provider=pending.provider,
                code_verifier=pending.code_verifier,
                nonce=pending.nonce,
                redirect_to=pending.redirect_to,
                expires_at=expires_at,
            )
        )

    async def pop(self, state_hash: str, now: datetime) -> PendingSignIn | None:
        # One statement, so reading and deleting are atomic: a state is used once.
        row = (
            await self._session.execute(
                delete(OAuthStateModel)
                .where(OAuthStateModel.state_hash == state_hash, OAuthStateModel.expires_at > now)
                .returning(
                    OAuthStateModel.provider,
                    OAuthStateModel.code_verifier,
                    OAuthStateModel.nonce,
                    OAuthStateModel.redirect_to,
                )
            )
        ).first()
        if row is None:
            return None
        return PendingSignIn(row.provider, row.code_verifier, row.nonce, row.redirect_to)


def session_to_entity(row: SessionModel) -> AuthSession:
    return AuthSession(
        id=row.id,
        user_id=UserId(row.user_id),
        token_hash=row.token_hash,
        created_at=row.created_at,
        last_seen_at=row.last_seen_at,
        idle_expires_at=row.idle_expires_at,
        absolute_expires_at=row.absolute_expires_at,
        revoked_at=row.revoked_at,
        user_agent=row.user_agent,
    )


class SqlSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, token_hash: str) -> AuthSession | None:
        row = await self._session.scalar(
            select(SessionModel).where(SessionModel.token_hash == token_hash)
        )
        return session_to_entity(row) if row else None

    async def get_with_user(self, token_hash: str) -> tuple[AuthSession, User] | None:
        result = await self._session.execute(
            select(SessionModel, UserModel)
            .join(UserModel, UserModel.id == SessionModel.user_id)
            .where(SessionModel.token_hash == token_hash)
        )
        found = result.first()
        if found is None:
            return None
        return session_to_entity(found[0]), user_to_entity(found[1])

    async def add(self, session: AuthSession) -> None:
        self._session.add(
            SessionModel(
                id=session.id,
                user_id=session.user_id.value,
                token_hash=session.token_hash,
                created_at=session.created_at,
                last_seen_at=session.last_seen_at,
                idle_expires_at=session.idle_expires_at,
                absolute_expires_at=session.absolute_expires_at,
                revoked_at=session.revoked_at,
                user_agent=session.user_agent,
            )
        )

    async def save(self, session: AuthSession) -> None:
        row = await self._session.get(SessionModel, session.id)
        if row is not None:
            row.last_seen_at = session.last_seen_at
            row.idle_expires_at = session.idle_expires_at
            row.revoked_at = session.revoked_at

    async def revoke_all_for_user(
        self, user_id: UserId, now: datetime, except_session_id: UUID | None = None
    ) -> None:
        statement = (
            update(SessionModel)
            .where(SessionModel.user_id == user_id.value, SessionModel.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        if except_session_id is not None:
            statement = statement.where(SessionModel.id != except_session_id)
        await self._session.execute(statement)

    async def delete_expired(self, now: datetime) -> None:
        await self._session.execute(
            delete(SessionModel)
            .where(SessionModel.absolute_expires_at <= now)
            .execution_options(synchronize_session=False)
        )


def token_to_entity(row: OneTimeTokenModel) -> OneTimeToken:
    return OneTimeToken(
        id=row.id,
        user_id=UserId(row.user_id),
        purpose=TokenPurpose(row.purpose),
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        used_at=row.used_at,
        created_at=row.created_at,
    )


class SqlOneTimeTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, token_hash: str, purpose: TokenPurpose) -> OneTimeToken | None:
        row = await self._session.scalar(
            select(OneTimeTokenModel)
            .where(
                OneTimeTokenModel.token_hash == token_hash,
                OneTimeTokenModel.purpose == purpose.value,
            )
            # Locked until commit: a second request with the same link waits, then sees it used.
            .with_for_update()
        )
        return token_to_entity(row) if row else None

    async def add(self, token: OneTimeToken) -> None:
        self._session.add(
            OneTimeTokenModel(
                id=token.id,
                user_id=token.user_id.value,
                purpose=token.purpose.value,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
                used_at=token.used_at,
                created_at=token.created_at,
            )
        )

    async def save(self, token: OneTimeToken) -> None:
        row = await self._session.get(OneTimeTokenModel, token.id)
        if row is not None:
            row.used_at = token.used_at

    async def invalidate_all(self, user_id: UserId, purpose: TokenPurpose, now: datetime) -> None:
        await self._session.execute(
            update(OneTimeTokenModel)
            .where(
                OneTimeTokenModel.user_id == user_id.value,
                OneTimeTokenModel.purpose == purpose.value,
                OneTimeTokenModel.used_at.is_(None),
            )
            .values(used_at=now)
        )

    async def delete_expired(self, now: datetime) -> None:
        await self._session.execute(
            delete(OneTimeTokenModel)
            .where(OneTimeTokenModel.expires_at <= now)
            .execution_options(synchronize_session=False)
        )
