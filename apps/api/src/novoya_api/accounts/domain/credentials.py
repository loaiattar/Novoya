from dataclasses import dataclass
from datetime import datetime

from novoya_api.accounts.domain.value_objects import PasswordHash, UserId


@dataclass(slots=True)
class PasswordCredential:
    """The hashed password of a user. A user has zero or one."""

    user_id: UserId
    password_hash: PasswordHash
    updated_at: datetime

    def replace(self, password_hash: PasswordHash, now: datetime) -> None:
        self.password_hash = password_hash
        self.updated_at = now
