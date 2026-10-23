from uuid import UUID

from novoya_api.planning.application.agent_view import compose_agent_plan
from novoya_api.planning.application.dto import AgentPlanView
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.domain.errors import PlanNotFound
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork


class TakePlan:
    """An agent claims a requested plan. Anyone else's take looks like an invalid transition."""

    def __init__(
        self,
        plans: PlanRepository,
        catalog: OfferCatalog,
        trips: TripBriefs,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._plans = plans
        self._catalog = catalog
        self._trips = trips
        self._uow = uow
        self._clock = clock

    async def __call__(self, plan_id: UUID, agent_id: UUID) -> AgentPlanView:
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        plan.take(agent_id, self._clock.now())
        await self._plans.save(plan)
        view = await compose_agent_plan(plan, self._catalog, self._trips)
        await self._uow.commit()
        return view
