import logging
from uuid import UUID

from novoya_api.planning.application.dto import (
    AgentPlanExtraView,
    AgentPlanItemView,
    AgentPlanView,
    OfferContact,
    QueueEntryView,
    TripBrief,
)
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.domain.plan import Plan

logger = logging.getLogger(__name__)


def queue_entry_as_view(plan: Plan, trip: TripBrief | None) -> QueueEntryView:
    """A waiting plan for the queue. The wish fields are empty when the wish is gone."""
    return QueueEntryView(
        id=plan.id,
        wish_id=plan.wish_id,
        status=plan.status.value,
        summary=plan.summary,
        updated_at=plan.updated_at,
        wish_text=trip.text if trip else "",
        country=trip.country if trip else None,
        city=trip.city if trip else None,
        persons=trip.persons if trip else None,
        start_date=trip.start_date if trip else None,
        end_date=trip.end_date if trip else None,
        budget_max=trip.budget_max if trip else None,
        currency=trip.currency if trip else None,
    )


async def compose_agent_plan(plan: Plan, catalog: OfferCatalog, trips: TripBriefs) -> AgentPlanView:
    """Prices, partners and the wish, as the assigned agent sees them."""
    offer_ids = [item.offer_id for item in plan.items]
    offers = {offer.id: offer for offer in await catalog.contacts_for(offer_ids)}
    briefs = await trips.for_wish_ids([plan.wish_id])
    return agent_plan_as_view(plan, offers, briefs.get(plan.wish_id))


def agent_plan_as_view(
    plan: Plan, offers: dict[UUID, OfferContact], trip: TripBrief | None
) -> AgentPlanView:
    """The plan as the assigned agent sees it: prices, partners, total, budget.

    Removed items stay visible so the agent can see what they dropped. A missing offer
    stays with available=false and no partner to call.
    """
    items: list[AgentPlanItemView] = []
    for item in plan.items:
        offer = offers.get(item.offer_id)
        if offer is None:
            logger.warning("plan %s: offer %s not found", plan.id, item.offer_id)
            items.append(
                AgentPlanItemView(
                    id=item.id,
                    offer_id=item.offer_id,
                    day=item.day,
                    quantity=item.quantity,
                    note=item.note,
                    kind=None,
                    title=None,
                    description=None,
                    available=False,
                    negotiated_price=item.negotiated_price,
                    removed=item.removed,
                    partner_name=None,
                    partner_contact_email=None,
                    partner_contact_phone=None,
                )
            )
            continue
        items.append(
            AgentPlanItemView(
                id=item.id,
                offer_id=item.offer_id,
                day=item.day,
                quantity=item.quantity,
                note=item.note,
                kind=offer.kind,
                title=offer.title,
                description=offer.description,
                available=True,
                negotiated_price=item.negotiated_price,
                removed=item.removed,
                partner_name=offer.partner_name,
                partner_contact_email=offer.partner_contact_email,
                partner_contact_phone=offer.partner_contact_phone,
            )
        )
    total = plan.priced_total()
    budget = trip.budget_max if trip else None
    return AgentPlanView(
        id=plan.id,
        wish_id=plan.wish_id,
        status=plan.status.value,
        summary=plan.summary,
        assigned_agent_id=plan.assigned_agent_id,
        items=tuple(items),
        extras=tuple(
            AgentPlanExtraView(
                extra.extra_id,
                extra.pricing,
                extra.price_eur,
                extra.label,
                extra.unit,
                needs_quantity_check=extra.needs_quantity_check,
                confirmed=extra.confirmed,
            )
            for extra in plan.extras
        ),
        total=total,
        ready_to_quote=plan.ready_to_quote(),
        budget_max=budget,
        currency=trip.currency if trip else None,
        over_budget=budget is not None and total > budget,
        wish_text=trip.text if trip else None,
        country=trip.country if trip else None,
        city=trip.city if trip else None,
        persons=trip.persons if trip else None,
        start_date=trip.start_date if trip else None,
        end_date=trip.end_date if trip else None,
    )
