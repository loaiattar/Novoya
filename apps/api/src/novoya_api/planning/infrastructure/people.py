from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import get_users, search_user_ids
from novoya_api.planning.application.dto import Person


class AccountPeople:
    """People through accounts.public, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_ids(self, query: str) -> list[UUID]:
        return await search_user_ids(query, session=self._session)

    async def get_many(self, user_ids: Sequence[UUID]) -> dict[UUID, Person]:
        users = await get_users(user_ids, session=self._session)
        return {
            user_id: Person(user.user_id, user.name, user.email) for user_id, user in users.items()
        }
