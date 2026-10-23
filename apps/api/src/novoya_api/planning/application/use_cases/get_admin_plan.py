from uuid import UUID

from novoya_api.planning.application.agent_view import compose_agent_plan
from novoya_api.planning.application.dto import AdminPlanView
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.people import People
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.domain.errors import PlanNotFound


class GetAdminPlan:
    """One plan, read-only, for an admin: the same view as the assigned agent's (prices,
    partners, total and budget), whoever took it, with the client and the agent."""

    def __init__(
        self, plans: PlanRepository, catalog: OfferCatalog, trips: TripBriefs, people: People
    ) -> None:
        self._plans = plans
        self._catalog = catalog
        self._trips = trips
        self._people = people

    async def __call__(self, plan_id: UUID) -> AdminPlanView:
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        view = await compose_agent_plan(plan, self._catalog, self._trips)
        trip = (await self._trips.for_wish_ids([plan.wish_id])).get(plan.wish_id)
        client_id = trip.user_id if trip else None
        people = await self._people.get_many(
            [user_id for user_id in (client_id, plan.assigned_agent_id) if user_id]
        )
        return AdminPlanView(
            plan=view,
            client=people.get(client_id) if client_id else None,
            agent=people.get(plan.assigned_agent_id) if plan.assigned_agent_id else None,
        )
