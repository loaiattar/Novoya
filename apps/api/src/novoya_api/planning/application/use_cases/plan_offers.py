from dataclasses import dataclass
from uuid import UUID

from novoya_api.planning.application.agent_view import compose_agent_plan
from novoya_api.planning.application.dto import (
    AgentOfferView,
    AgentPlanView,
    OfferSummary,
    TripBrief,
)
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.domain.errors import InvalidPlan, PlanNotFound
from novoya_api.planning.domain.plan import Plan, item_fits
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork
from novoya_api.shared.domain.errors import PermissionDenied


class ListPlanOffers:
    """The offers the assigned agent may add to the plan (#184): listed, taking the trip's
    travellers, open on at least one of its days, best first. Anyone else is forbidden."""

    def __init__(self, plans: PlanRepository, catalog: OfferCatalog, trips: TripBriefs) -> None:
        self._plans = plans
        self._catalog = catalog
        self._trips = trips

    async def __call__(self, plan_id: UUID, agent_id: UUID) -> list[AgentOfferView]:
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        if plan.assigned_agent_id != agent_id:
            raise PermissionDenied("only the assigned agent can see this plan")
        trip = (await self._trips.for_wish_ids([plan.wish_id])).get(plan.wish_id)
        offers, _days = await _fitting(self._catalog, trip)
        partners = {
            offer.id: offer.partner_name
            for offer in await self._catalog.contacts_for([offer.id for offer in offers])
        }
        return [
            AgentOfferView(
                id=offer.id,
                kind=offer.kind,
                title=offer.title,
                description=offer.description,
                partner_name=partners.get(offer.id, ""),
                open_days=tuple(sorted(offer.open_days)),
            )
            for offer in offers
        ]


@dataclass(frozen=True)
class AddItemCommand:
    plan_id: UUID
    agent_id: UUID
    offer_id: UUID
    day: int
    quantity: int
    note: str | None


class AddPlanItem:
    """The assigned agent adds an offer to the plan, with no price yet: on a custom plan to
    build it, on any other to complete it. The offer must fit the trip's travellers and be
    open on the item's days (#182), as for the plans the app builds. Only while negotiating."""

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

    async def __call__(self, cmd: AddItemCommand) -> AgentPlanView:
        plan = await self._plans.get(cmd.plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        # First, so another agent learns nothing about the trip: 403 or 409 before any 422.
        item = plan.add_item(
            cmd.offer_id, cmd.day, cmd.quantity, cmd.note, cmd.agent_id, self._clock.now()
        )
        trip = (await self._trips.for_wish_ids([plan.wish_id])).get(plan.wish_id)
        offers, trip_days = await _fitting(self._catalog, trip)
        offer = next((o for o in offers if o.id == cmd.offer_id), None)
        if offer is None:
            raise InvalidPlan("this offer does not fit the trip's travellers and dates")
        hotel = offer.kind == "hotel"
        if not item_fits(hotel, item.day, item.quantity, offer.open_days, trip_days):
            raise InvalidPlan("the offer is not open on these days of the trip")
        await self._plans.add_item(plan, item.id)
        return await self._view(plan)

    async def _view(self, plan: Plan) -> AgentPlanView:
        fresh = await self._plans.get(plan.id)
        if fresh is None:
            raise PlanNotFound("no such plan")
        view = await compose_agent_plan(fresh, self._catalog, self._trips)
        await self._uow.commit()
        return view


async def _fitting(catalog: OfferCatalog, trip: TripBrief | None) -> tuple[list[OfferSummary], int]:
    """The offers fitting the trip of the plan, and its number of days; none when its wish
    lost its place or dates."""
    if (
        trip is None
        or trip.country is None
        or trip.persons is None
        or trip.start_date is None
        or trip.end_date is None
    ):
        return [], 0
    offers = await catalog.fitting_offers(
        trip.country, trip.city, (), trip.persons, trip.start_date, trip.end_date
    )
    return offers, (trip.end_date - trip.start_date).days + 1
