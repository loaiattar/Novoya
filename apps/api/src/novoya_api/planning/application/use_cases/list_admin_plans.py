from uuid import UUID

from novoya_api.planning.application.dto import AdminPlanEntryView, Person, TripBrief
from novoya_api.planning.application.ports.people import People
from novoya_api.planning.application.ports.plan_repository import (
    QUEUE_CAP,
    QUEUE_PAGE,
    PlanRepository,
)
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.application.ports.wish_search import WishSearch
from novoya_api.planning.domain.plan import Plan, PlanStatus


class ListAdminPlans:
    """Every client's plans, last changed first, for the admin overview: who asked, where to,
    which agent has it. The search matches the client's email or name, or the destination."""

    def __init__(
        self, plans: PlanRepository, trips: TripBriefs, wishes: WishSearch, people: People
    ) -> None:
        self._plans = plans
        self._trips = trips
        self._wishes = wishes
        self._people = people

    async def __call__(
        self,
        status: PlanStatus | None = None,
        query: str | None = None,
        wish_id: UUID | None = None,
        *,
        limit: int = QUEUE_PAGE,
        offset: int = 0,
    ) -> list[AdminPlanEntryView]:
        wish_ids: list[UUID] | None = None
        query = query.strip() if query else None
        if query:
            wish_ids = await self._wishes.matching(query, await self._people.search_ids(query))
        if wish_id is not None:
            wish_ids = [wish_id] if wish_ids is None or wish_id in wish_ids else []
        if wish_ids == []:
            return []
        plans = await self._plans.search(
            [status] if status else [],
            wish_ids,
            limit=min(max(limit, 1), QUEUE_CAP),
            offset=max(offset, 0),
        )
        trips = await self._trips.for_wish_ids([plan.wish_id for plan in plans])
        people = await self._people.get_many(
            [trip.user_id for trip in trips.values() if trip.user_id]
            + [plan.assigned_agent_id for plan in plans if plan.assigned_agent_id]
        )
        return [_entry(plan, trips.get(plan.wish_id), people) for plan in plans]


def _entry(plan: Plan, trip: TripBrief | None, people: dict[UUID, Person]) -> AdminPlanEntryView:
    client_id = trip.user_id if trip else None
    return AdminPlanEntryView(
        id=plan.id,
        wish_id=plan.wish_id,
        status=plan.status.value,
        summary=plan.summary,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        country=trip.country if trip else None,
        city=trip.city if trip else None,
        persons=trip.persons if trip else None,
        start_date=trip.start_date if trip else None,
        end_date=trip.end_date if trip else None,
        client=people.get(client_id) if client_id else None,
        agent=people.get(plan.assigned_agent_id) if plan.assigned_agent_id else None,
    )
