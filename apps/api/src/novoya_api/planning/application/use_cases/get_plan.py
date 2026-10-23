from uuid import UUID

from novoya_api.planning.application.dto import PlanView
from novoya_api.planning.application.plan_view import plan_as_view
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.application.ports.wish_ownership import WishOwnership
from novoya_api.planning.domain.errors import PlanNotFound


class GetPlan:
    """The plan as the owner sees it. Anyone else, or a missing id, looks the same: not found."""

    def __init__(self, plans: PlanRepository, catalog: OfferCatalog, wishes: WishOwnership) -> None:
        self._plans = plans
        self._catalog = catalog
        self._wishes = wishes

    async def __call__(self, plan_id: UUID, reader_id: UUID) -> PlanView:
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        owner_id = await self._wishes.owner_id(plan.wish_id)
        if owner_id is None or owner_id != reader_id:
            raise PlanNotFound("no such plan")
        kept_ids = [item.offer_id for item in plan.items if not item.removed]
        offers = {offer.id: offer for offer in await self._catalog.summaries_for(kept_ids)}
        return plan_as_view(plan, offers)
