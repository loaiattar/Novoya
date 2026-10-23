from typing import Protocol

from novoya_api.accounts.domain.value_objects import UserId


class UserDataEraser(Protocol):
    async def erase(self, user_id: UserId) -> None:
        """Erases what the other modules keep about this client: quotes, plans, wishes.
        Before the user row, in the same transaction; the caller commits."""
        ...
