from novoya_api.accounts.application.ports.repositories import UserRepository
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import User


class ListUsers:
    """The users, newest first, filtered by email or name and by role. For admins."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def __call__(
        self, query: str | None, role: Role | None, limit: int, offset: int
    ) -> list[User]:
        return await self._users.search(query, role, limit, offset)
