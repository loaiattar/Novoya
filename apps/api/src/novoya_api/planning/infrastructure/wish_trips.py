from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.planning.application.dto import TripBrief
from novoya_api.wishes.public import trips


class WishTrips:
    """TripBriefs through wishes.public, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def for_wish_ids(self, wish_ids: Sequence[UUID]) -> dict[UUID, TripBrief]:
        found = await trips(wish_ids, session=self._session)
        return {
            wish_id: TripBrief(
                wish_id=brief.wish_id,
                text=brief.text,
                country=brief.country,
                city=brief.city,
                budget_max=brief.budget_max,
                currency=brief.currency,
                persons=brief.persons,
                start_date=brief.start_date,
                end_date=brief.end_date,
                tags=brief.tags,
                user_id=brief.user_id,
            )
            for wish_id, brief in found.items()
        }
