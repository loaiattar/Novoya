from uuid import UUID

from novoya_api.planning.application.dto import PricedPlan
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.application.ports.wish_ownership import WishOwnership
from novoya_api.planning.application.priced_plan import priced


class GetPricedPlan:
    """A quoted plan as its quote shows it, for quoting to read back. Read only. None when
    the plan, its wish or its agent is gone, or when it is not quoted yet."""

    def __init__(
        self,
        plans: PlanRepository,
        catalog: OfferCatalog,
        trips: TripBriefs,
        wishes: WishOwnership,
    ) -> None:
        self._plans = plans
        self._catalog = catalog
        self._trips = trips
        self._wishes = wishes

    async def __call__(self, plan_id: UUID) -> PricedPlan | None:
        plan = await self._plans.get(plan_id)
        if plan is None or not plan.is_quoted() or plan.assigned_agent_id is None:
            return None
        client_id = await self._wishes.owner_id(plan.wish_id)
        if client_id is None:
            return None
        return await priced(plan, client_id, plan.assigned_agent_id, self._catalog, self._trips)
