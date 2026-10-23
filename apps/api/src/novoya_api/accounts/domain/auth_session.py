from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from novoya_api.accounts.domain.value_objects import UserId

TOUCH_INTERVAL = timedelta(minutes=5)


@dataclass(slots=True)
class AuthSession:
    """A signed-in browser. Named so to avoid confusion with the database session."""

    id: UUID
    user_id: UserId
    token_hash: str
    created_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None
    user_agent: str | None  # no IP address: we store as little as we can (GDPR)

    @classmethod
    def open(
        cls,
        user_id: UserId,
        token_hash: str,
        now: datetime,
        idle_ttl: timedelta,
        absolute_ttl: timedelta,
        user_agent: str | None,
    ) -> "AuthSession":
        return cls(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            created_at=now,
            last_seen_at=now,
            idle_expires_at=now + idle_ttl,
            absolute_expires_at=now + absolute_ttl,
            revoked_at=None,
            user_agent=user_agent,
        )

    def is_active(self, now: datetime) -> bool:
        return (
            self.revoked_at is None
            and now < self.idle_expires_at
            and now < self.absolute_expires_at
        )

    def touch(self, now: datetime, idle_ttl: timedelta) -> bool:
        """Extend the idle expiry. Return True when it changed and must be saved."""
        if now - self.last_seen_at < TOUCH_INTERVAL:
            return False  # do not write to the database on every request
        self.last_seen_at = now
        self.idle_expires_at = min(now + idle_ttl, self.absolute_expires_at)
        return True

    def revoke(self, now: datetime) -> None:
        if self.revoked_at is None:
            self.revoked_at = now
