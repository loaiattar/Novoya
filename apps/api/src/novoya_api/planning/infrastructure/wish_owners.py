from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.wishes.public import owner_id


class WishOwners:
    """WishOwnership through wishes.public, in the request's session.

    With lock_for, a wish that user owns is read FOR SHARE until the transaction ends: a
    quote request then waits for a preference removal in progress on that wish (#165), and a
    removal waits for the request, so it never misses a plan that just left proposed. Another
    user's wish is never locked."""

    def __init__(self, session: AsyncSession, *, lock_for: UUID | None = None) -> None:
        self._session = session
        self._lock_for = lock_for

    async def owner_id(self, wish_id: UUID) -> UUID | None:
        return await owner_id(wish_id, session=self._session, lock_for=self._lock_for)
