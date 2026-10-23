from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from novoya_api.planning.application.agent_view import compose_agent_plan
from novoya_api.planning.application.dto import AgentPlanView
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.plan_repository import ItemWrite, PlanRepository
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.domain.errors import InvalidPlan, PlanNotFound
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class SetItemCommand:
    plan_id: UUID
    item_id: UUID
    agent_id: UUID
    negotiated_price: Decimal | None
    removed: bool | None


class SetItemPrice:
    """The assigned agent sets a negotiated price, drops an item, or puts it back."""

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

    async def __call__(self, cmd: SetItemCommand) -> AgentPlanView:
        plan = await self._plans.get(cmd.plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        now = self._clock.now()
        write = self._apply(plan, cmd, now)
        if write is not None:
            await self._plans.save_item(plan, cmd.item_id, write)
        fresh = await self._plans.get(cmd.plan_id)
        if fresh is None:
            raise PlanNotFound("no such plan")
        view = await compose_agent_plan(fresh, self._catalog, self._trips)
        await self._uow.commit()
        return view

    def _apply(self, plan, cmd: SetItemCommand, now) -> ItemWrite | None:
        if cmd.negotiated_price is not None and cmd.removed is not None:
            raise InvalidPlan("set a price or set removed, not both")
        if cmd.removed is True:
            already = _removed(plan, cmd.item_id)
            plan.remove_item(cmd.item_id, cmd.agent_id, now)
            return None if already else ItemWrite.REMOVE
        if cmd.removed is False:
            already = _removed(plan, cmd.item_id)
            plan.restore_item(cmd.item_id, cmd.agent_id, now)
            return ItemWrite.RESTORE if already else None
        if cmd.negotiated_price is None:
            raise InvalidPlan("set a price or set removed")
        plan.set_item_price(cmd.item_id, cmd.agent_id, cmd.negotiated_price, now)
        return ItemWrite.PRICE


def _removed(plan, item_id: UUID) -> bool:
    for item in plan.items:
        if item.id == item_id:
            return item.removed
    raise PlanNotFound("no such item")
