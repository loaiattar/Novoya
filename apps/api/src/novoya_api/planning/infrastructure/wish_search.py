from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.wishes.public import search_ids


class WishesSearch:
    """WishSearch through wishes.public, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def matching(self, query: str, user_ids: Sequence[UUID]) -> list[UUID]:
        return await search_ids(query, user_ids, session=self._session)
