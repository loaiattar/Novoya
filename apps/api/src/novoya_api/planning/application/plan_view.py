import logging
from uuid import UUID

from novoya_api.planning.application.dto import OfferSummary, PlanItemView, PlanView
from novoya_api.planning.domain.plan import Plan

logger = logging.getLogger(__name__)


def plan_as_view(plan: Plan, offers: dict[UUID, OfferSummary]) -> PlanView:
    """The plan as the client sees it: never a price, never a partner, no removed items.

    A missing offer stays on the day with available=false, so the client can say it is gone.
    """
    items: list[PlanItemView] = []
    for item in plan.items:
        if item.removed:
            continue
        offer = offers.get(item.offer_id)
        if offer is None:
            logger.warning("plan %s: offer %s not found", plan.id, item.offer_id)
            items.append(
                PlanItemView(
                    id=item.id,
                    offer_id=item.offer_id,
                    day=item.day,
                    quantity=item.quantity,
                    note=item.note,
                    kind=None,
                    title=None,
                    description=None,
                    available=False,
                )
            )
            continue
        items.append(
            PlanItemView(
                id=item.id,
                offer_id=item.offer_id,
                day=item.day,
                quantity=item.quantity,
                note=item.note,
                kind=offer.kind,
                title=offer.title,
                description=offer.description,
                available=True,
            )
        )
    return PlanView(
        id=plan.id,
        wish_id=plan.wish_id,
        status=plan.status.value,
        based_on_preferences=plan.based_on_preferences,
        summary=plan.summary,
        items=tuple(items),
        custom=plan.custom,
    )
