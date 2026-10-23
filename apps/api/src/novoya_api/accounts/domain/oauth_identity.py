from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from novoya_api.accounts.domain.value_objects import Email, UserId


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    """Who the provider says the person is, read from its checked ID token."""

    provider: str
    subject: str  # the provider's stable id for the person ("sub"), not the email
    email: Email
    email_verified: bool
    # True when the provider owns the address (Gmail, or a Workspace domain), so a verified
    # email proves who holds it today. Only then may it be linked to an existing account.
    email_authoritative: bool
    name: str | None
    first_name: str | None
    last_name: str | None
    locale: str | None


@dataclass(slots=True)
class OAuthIdentity:
    """A provider account linked to a user. A user has zero or more, one per provider."""

    id: UUID
    user_id: UserId
    provider: str
    subject: str
    created_at: datetime
    last_login_at: datetime

    @classmethod
    def link(cls, user_id: UserId, external: ExternalIdentity, now: datetime) -> "OAuthIdentity":
        return cls(uuid4(), user_id, external.provider, external.subject, now, now)

    def touch(self, now: datetime) -> None:
        self.last_login_at = now
