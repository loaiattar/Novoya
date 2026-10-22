"""ORM tables of the accounts module. They are not the entities: repositories.py maps them."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from novoya_api.shared.infrastructure.db.base import Base

Timestamp = DateTime(timezone=True)


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('client', 'agent', 'admin', 'super_admin')", name="ck_users_role"
        ),
        CheckConstraint("locale IN ('en', 'fr')", name="ck_users_locale"),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # always stored lowercased
    name: Mapped[str | None] = mapped_column(String(200))
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), index=True, server_default="client")
    locale: Mapped[str] = mapped_column(String(2), server_default="en")
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    # The last status change (#128): the admin who made it, kept as NULL once they are deleted.
    status_changed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status_changed_at: Mapped[datetime | None] = mapped_column(Timestamp)
    email_verified_at: Mapped[datetime | None] = mapped_column(Timestamp)
    created_at: Mapped[datetime] = mapped_column(Timestamp)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp, server_default=func.now(), onupdate=func.now()
    )


class PasswordCredentialModel(Base):
    __tablename__ = "password_credentials"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(Timestamp)


class SessionModel(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index(
            "ix_sessions_open_by_user",
            "user_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp)
    last_seen_at: Mapped[datetime] = mapped_column(Timestamp)
    idle_expires_at: Mapped[datetime] = mapped_column(Timestamp)
    # Indexed: each sign-in deletes the sessions past it (no full scan as the table grows).
    absolute_expires_at: Mapped[datetime] = mapped_column(Timestamp, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(Timestamp)
    user_agent: Mapped[str | None] = mapped_column(String(512))


class OneTimeTokenModel(Base):
    __tablename__ = "one_time_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')",
            name="ck_one_time_tokens_purpose",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(30))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Indexed: each new link deletes the expired ones.
    expires_at: Mapped[datetime] = mapped_column(Timestamp, index=True)
    used_at: Mapped[datetime | None] = mapped_column(Timestamp)
    created_at: Mapped[datetime] = mapped_column(Timestamp)


class RoleChangeModel(Base):
    __tablename__ = "role_changes"
    __table_args__ = (
        CheckConstraint("source IN ('admin_api', 'cmd_grant_role')", name="ck_role_changes_source"),
        CheckConstraint(
            "old_role IN ('client', 'agent', 'admin', 'super_admin')",
            name="ck_role_changes_old_role",
        ),
        CheckConstraint(
            "new_role IN ('client', 'agent', 'admin', 'super_admin')",
            name="ck_role_changes_new_role",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    old_role: Mapped[str] = mapped_column(String(20))
    new_role: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(20))
    changed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    changed_at: Mapped[datetime] = mapped_column(Timestamp)


class OAuthIdentityModel(Base):
    __tablename__ = "oauth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_oauth_identities_provider_subject"),
        # One account per provider and user: two Google accounts linked at the same moment
        # cannot both pass the check in the use case.
        UniqueConstraint("user_id", "provider", name="uq_oauth_identities_user_provider"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(255))  # Google's "sub"
    created_at: Mapped[datetime] = mapped_column(Timestamp)
    last_login_at: Mapped[datetime] = mapped_column(Timestamp)


class OAuthStateModel(Base):
    """A sign-in on its way to the provider and back: 10 minutes at most, read once."""

    __tablename__ = "oauth_states"

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    code_verifier: Mapped[str] = mapped_column(String(128))
    nonce: Mapped[str] = mapped_column(String(128))
    redirect_to: Mapped[str] = mapped_column(String(512))
    expires_at: Mapped[datetime] = mapped_column(Timestamp, index=True)
