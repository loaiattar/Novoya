from uuid import UUID

from novoya_api.planning.application.dto import PricedExtra, PricedItem, PricedPlan
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.domain.plan import Plan


async def priced(
    plan: Plan, client_id: UUID, agent_id: UUID, catalog: OfferCatalog, trips: TripBriefs
) -> PricedPlan:
    """The plan as its quote shows it: kept items by day with their prices, the extras, the
    total and the trip. Call it on a plan that is ready to quote, or already quoted."""
    kept = sorted((item for item in plan.items if not item.removed), key=lambda i: i.day)
    offers = {
        offer.id: offer for offer in await catalog.summaries_for([item.offer_id for item in kept])
    }
    trip = (await trips.for_wish_ids([plan.wish_id])).get(plan.wish_id)
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
