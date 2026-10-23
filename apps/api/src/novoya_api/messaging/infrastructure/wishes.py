from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.wishes.public import owner_id


class ModuleWishes:
    """Wishes through wishes.public, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def owner_id(self, wish_id: UUID) -> UUID | None:
        return await owner_id(wish_id, session=self._session)
