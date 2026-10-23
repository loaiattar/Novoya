from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.planning.public import plans_for_wishes
from novoya_api.quoting.public import quotes_for_plans
from novoya_api.trips.application.dto import PlanSummary, WishSummary
from novoya_api.wishes.public import wishes_for_user


class WishesOfUser:
    """TripWishes through wishes.public, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def of_user(self, user_id: UUID) -> list[WishSummary]:
        wishes = await wishes_for_user(user_id, session=self._session)
        return [
            WishSummary(
                wish_id=wish.wish_id,
                text=wish.text,
                status=wish.status,
                country=wish.country,
                city=wish.city,
                persons=wish.persons,
                start_date=wish.start_date,
                end_date=wish.end_date,
                created_at=wish.created_at,
            )
            for wish in wishes
        ]


class PlansOfWishes:
    """TripPlans through planning.public, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def for_wishes(self, wish_ids: Sequence[UUID]) -> dict[UUID, PlanSummary]:
        plans = await plans_for_wishes(wish_ids, session=self._session)
        return {wish_id: PlanSummary(plan.plan_id, plan.status) for wish_id, plan in plans.items()}


class QuotesOfPlans:
    """TripQuotes through quoting.public, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def for_plans(self, plan_ids: Sequence[UUID]) -> dict[UUID, UUID]:
        return await quotes_for_plans(plan_ids, session=self._session)
