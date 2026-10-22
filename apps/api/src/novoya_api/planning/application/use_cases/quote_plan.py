from uuid import UUID

from novoya_api.planning.application.dto import PricedExtra, PricedItem, PricedPlan
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.application.ports.wish_ownership import WishOwnership
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

        kept = sorted((item for item in plan.items if not item.removed), key=lambda i: i.day)
        offers = {
            offer.id: offer
            for offer in await self._catalog.summaries_for([item.offer_id for item in kept])
        }
        trip = (await self._trips.for_wish_ids([plan.wish_id])).get(plan.wish_id)
        items = []
        for item in kept:
            offer = offers.get(item.offer_id)
            items.append(
                PricedItem(
                    day=item.day,
                    kind=offer.kind if offer else None,
                    title=offer.title if offer else None,
                    description=offer.description if offer else None,
                    quantity=item.quantity,
                    price=item.negotiated_price,  # ready_to_quote(): never None here
                )
            )
        return PricedPlan(
            plan_id=plan.id,
            wish_id=plan.wish_id,
            client_id=client_id,
            agent_id=agent_id,
            summary=plan.summary,
            items=tuple(items),
            extras=tuple(
                PricedExtra(
                    label=extra.label,
                    unit=extra.unit,
                    pricing=extra.pricing,
                    price=None if extra.pricing == "included" else extra.price_eur,
                )
                for extra in plan.extras
            ),
            total=plan.priced_total(),
            wish_text=trip.text if trip else "",
            country=trip.country if trip else None,
            city=trip.city if trip else None,
            persons=trip.persons if trip else None,
            start_date=trip.start_date if trip else None,
            end_date=trip.end_date if trip else None,
            budget_max=trip.budget_max if trip else None,
            currency=trip.currency if trip else None,
            tags=trip.tags if trip else (),
        )
