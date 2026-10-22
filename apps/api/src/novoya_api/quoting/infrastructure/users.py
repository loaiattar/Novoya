from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import get_user, get_users, search_user_ids
from novoya_api.quoting.application.dto import Person


class AccountPeople:
    """People through accounts.public, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> Person | None:
        user = await get_user(user_id, session=self._session)
        if user is None:
            return None
        return Person(user.user_id, user.name, user.email, user.locale)

    async def get_many(self, user_ids: Sequence[UUID]) -> dict[UUID, Person]:
        users = await get_users(user_ids, session=self._session)
        return {
            user_id: Person(user.user_id, user.name, user.email, user.locale)
            for user_id, user in users.items()
        }

    async def search_ids(self, query: str) -> list[UUID]:
        return await search_user_ids(query, session=self._session)
