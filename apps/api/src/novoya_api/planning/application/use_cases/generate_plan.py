from uuid import UUID

from novoya_api.planning.application.dto import OfferSummary, PlanRequest, PlanView
from novoya_api.planning.application.plan_view import plan_as_view
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.application.ports.plan_writer import PlanWriter
from novoya_api.planning.domain.errors import NoOfferFits
from novoya_api.planning.domain.plan import DraftItem, Plan, keep_valid, tidy
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork

FALLBACK_SUMMARY = (
    "A first plan built from our partners' offers that fit your group and dates. "
    "An agent will adjust it with you when you ask for a quote."
)


class GeneratePlan:
    """Build the proposed plan of an answered wish and add it. The caller commits.

    The read ends before the model writes, so no connection is held while it thinks: call it
    before the caller writes anything, and keep the caller's state outside the session.

    The writer may use an LLM, but the catalog decides what is allowed: every item must
    point to a listed offer that fits the travellers and is open on each day it covers
    (#182): an activity on its day, a hotel on each of its nights. When the writer
    fails, or none of its items is allowed, the plan is built from the best fitting offers,
    so a client always gets a plan."""

    def __init__(
        self,
        catalog: OfferCatalog,
        writer: PlanWriter,
        plans: PlanRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._catalog = catalog
        self._writer = writer
        self._plans = plans
        self._uow = uow
        self._clock = clock

    async def __call__(self, request: PlanRequest) -> PlanView:
        # Checked first so the client gets 422 without waiting for a model run.
        if not await self._fitting(request, ()):
            raise NoOfferFits("no listed offer fits the travellers and dates")
        # Nothing to save yet: end the read so the connection is not held while the model writes.
        await self._uow.rollback()

        draft = await self._writer.write(request)
        # The model may take a minute: read the catalog again, so an offer deactivated or
        # booked out meanwhile is neither kept nor used by the fallback.
        allowed = await self._fitting(request, ())
        if not allowed:
            raise NoOfferFits("no listed offer fits the travellers and dates")
        ranked = await self._fitting(request, request.tags) if request.tags else []
        offers = {offer.id: offer for offer in [*allowed, *ranked]}
        hotels = {offer.id for offer in offers.values() if offer.kind == "hotel"}

        open_days = {offer.id: offer.open_days for offer in offers.values()}
        valid = keep_valid(draft.items, open_days, hotels, request.trip_days) if draft else []
        items = tidy(valid, hotels, request.trip_days, open_days)
        # The model's summary describes all its items: keep it only if none was rejected or cut.
        summary = draft.summary if draft and items == list(draft.items) else FALLBACK_SUMMARY
        if not items:
            summary = FALLBACK_SUMMARY
            items = _fallback_items(ranked, allowed, request.trip_days)
        if not items:
            # Every fitting offer is a hotel that can't be booked every night: nothing to plan.
            raise NoOfferFits("no listed offer fits the travellers and dates")

        plan = Plan.propose(
            request.wish_id,
            bool(request.tags),
            summary,
            items,
            request.trip_days,
            self._clock.now(),
        )
        await self._plans.add(plan)
        return plan_as_view(plan, offers)

    async def _fitting(self, request: PlanRequest, tags: tuple[str, ...]) -> list[OfferSummary]:
        return await self._catalog.fitting_offers(
            request.country,
            request.city,
            tags,
            request.persons,
            request.start_date,
            request.end_date,
        )


def plannable(offers: list[OfferSummary], trip_days: int) -> bool:
    """Whether a plan can be built from these fitting offers whatever the model does: the
    fallback's own rule, so a "yes" here never ends in no_offer_fits (#183)."""
    return bool(_fallback_items([], offers, trip_days))


def _fallback_items(
    ranked: list[OfferSummary], allowed: list[OfferSummary], trip_days: int
) -> list[DraftItem]:
    """A hotel for every night, then one other offer a day, best first, each only on days it
    is open (#182). The hotel may come from any fitting offer: a trip needs a bed even when no
    hotel matches the tags, but it must be open every night, or the plan has no hotel."""
    items: list[DraftItem] = []
    stay = max(1, trip_days - 1)  # a one-day trip still books its hotel for a night
    nights = set(range(1, stay + 1))
    hotels = (offer for offer in [*ranked, *allowed] if offer.kind == "hotel")
    hotel = next((offer for offer in hotels if nights <= offer.open_days), None)
    if hotel:
        items.append(DraftItem(hotel.id, 1, stay, None))
    others = [offer for offer in ranked or allowed if offer.kind != "hotel"]
    used: set[UUID] = set()
    for day in range(1, trip_days + 1):
        offer = next((o for o in others if o.id not in used and day in o.open_days), None)
        if offer:
            used.add(offer.id)
            items.append(DraftItem(offer.id, day, 1, None))
    return items
