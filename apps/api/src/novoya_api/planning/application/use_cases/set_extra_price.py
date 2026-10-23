from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from novoya_api.planning.application.agent_view import compose_agent_plan
from novoya_api.planning.application.dto import AgentPlanView
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.domain.errors import PlanNotFound
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class SetExtraCommand:
    plan_id: UUID
    extra_id: UUID
    agent_id: UUID
    price_eur: Decimal


class SetExtraPrice:
    """The assigned agent prices an on_quote extra, or adjusts a supplement."""

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

    async def __call__(self, cmd: SetExtraCommand) -> AgentPlanView:
        plan = await self._plans.get(cmd.plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        plan.set_extra_price(cmd.extra_id, cmd.agent_id, cmd.price_eur, self._clock.now())
        await self._plans.save_extra(plan, cmd.extra_id)
        fresh = await self._plans.get(cmd.plan_id)
        if fresh is None:
            raise PlanNotFound("no such plan")
        view = await compose_agent_plan(fresh, self._catalog, self._trips)
        await self._uow.commit()
        return view
