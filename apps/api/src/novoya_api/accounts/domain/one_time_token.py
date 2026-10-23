from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from novoya_api.accounts.domain.errors import InvalidOrExpiredToken
from novoya_api.accounts.domain.value_objects import UserId


class TokenPurpose(StrEnum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


TOKEN_TTL = {
    TokenPurpose.EMAIL_VERIFICATION: timedelta(hours=24),
    TokenPurpose.PASSWORD_RESET: timedelta(minutes=30),
}


@dataclass(slots=True)
class OneTimeToken:
    """A link sent by email: used once, before it expires, for one purpose."""

    id: UUID
    user_id: UserId
    purpose: TokenPurpose
    token_hash: str
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime

    @classmethod
    def issue(
        cls, user_id: UserId, purpose: TokenPurpose, token_hash: str, now: datetime
    ) -> "OneTimeToken":
        return cls(uuid4(), user_id, purpose, token_hash, now + TOKEN_TTL[purpose], None, now)

    def consume(self, now: datetime) -> None:
        if self.used_at is not None or now >= self.expires_at:
            raise InvalidOrExpiredToken("this link is invalid or has expired")
        self.used_at = now
