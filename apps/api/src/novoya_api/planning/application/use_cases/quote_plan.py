from uuid import UUID

from novoya_api.planning.application.dto import PricedPlan
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.application.ports.wish_ownership import WishOwnership
from novoya_api.planning.application.priced_plan import priced
from novoya_api.planning.domain.errors import PlanNotFound, PlanNotReady
from novoya_api.shared.application.clock import Clock


class QuotePlan:
    """The assigned agent sends the quote: the plan becomes quoted and its prices are final.

    Called by quoting, which saves the quote in the same session. No commit here: the plan
    and its quote are written together or not at all."""

    def __init__(
        self,
        plans: PlanRepository,
        catalog: OfferCatalog,
        trips: TripBriefs,
        wishes: WishOwnership,
        clock: Clock,
    ) -> None:
        self._plans = plans
        self._catalog = catalog
        self._trips = trips
        self._wishes = wishes
        self._clock = clock

    async def __call__(self, plan_id: UUID, agent_id: UUID) -> PricedPlan:
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        client_id = await self._wishes.owner_id(plan.wish_id)
        if client_id is None:
            raise PlanNotFound("the plan's wish is gone")
        plan.mark_quoted(agent_id, self._clock.now())
        await self._plans.save(plan)
        # save() now holds the plan row, so no price edit can land any more. One may have
        # landed between get() and save(): read the prices again and quote those.
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        if not plan.ready_to_quote():
            raise PlanNotReady("an item changed meanwhile, reload the plan")
        return await priced(plan, client_id, agent_id, self._catalog, self._trips)
