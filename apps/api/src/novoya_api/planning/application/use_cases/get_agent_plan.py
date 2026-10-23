from uuid import UUID

from novoya_api.planning.application.agent_view import compose_agent_plan
from novoya_api.planning.application.dto import AgentPlanView
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.domain.errors import PlanNotFound
from novoya_api.shared.domain.errors import PermissionDenied


class GetAgentPlan:
    """The plan as the assigned agent sees it.

    Anyone else is forbidden; a missing id is not found."""

    def __init__(self, plans: PlanRepository, catalog: OfferCatalog, trips: TripBriefs) -> None:
        self._plans = plans
        self._catalog = catalog
        self._trips = trips

    async def __call__(self, plan_id: UUID, agent_id: UUID) -> AgentPlanView:
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        if plan.assigned_agent_id != agent_id:
            raise PermissionDenied("only the assigned agent can see this plan")
        return await compose_agent_plan(plan, self._catalog, self._trips)
