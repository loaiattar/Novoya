from uuid import UUID

from novoya_api.trips.application.dto import PlanSummary, TripView, WishSummary
from novoya_api.trips.application.ports.sources import TripPlans, TripQuotes, TripWishes


class ListMyTrips:
    """The client's wishes, newest first, each with its plan and its quote when they exist.
    Only this client's own wishes: the wishes are read by owner."""

    def __init__(self, wishes: TripWishes, plans: TripPlans, quotes: TripQuotes) -> None:
        self._wishes = wishes
        self._plans = plans
        self._quotes = quotes

    async def __call__(self, user_id: UUID) -> list[TripView]:
        wishes = await self._wishes.of_user(user_id)
        plans = await self._plans.for_wishes([wish.wish_id for wish in wishes])
        quotes = await self._quotes.for_plans([plan.plan_id for plan in plans.values()])
        return [_view(wish, plans.get(wish.wish_id), quotes) for wish in wishes]


def _view(wish: WishSummary, plan: PlanSummary | None, quotes: dict[UUID, UUID]) -> TripView:
    return TripView(
        wish_id=wish.wish_id,
        text=wish.text,
        status=wish.status,
        country=wish.country,
        city=wish.city,
        persons=wish.persons,
        start_date=wish.start_date,
        end_date=wish.end_date,
        created_at=wish.created_at,
        plan_id=plan.plan_id if plan else None,
        plan_status=plan.status if plan else None,
        quote_id=quotes.get(plan.plan_id) if plan else None,
    )
