"""ListPlanOffers and AddPlanItem (#184) are tested with fake ports: no database."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from novoya_api.planning.application.dto import OfferContact, OfferSummary, TripBrief
from novoya_api.planning.application.use_cases.plan_offers import (
    AddItemCommand,
    AddPlanItem,
    ListPlanOffers,
)
from novoya_api.planning.domain.errors import InvalidPlan, PlanNotFound
from novoya_api.planning.domain.plan import Plan
from novoya_api.shared.domain.errors import InvalidTransition, PermissionDenied

WISH_ID = UUID("00000000-0000-0000-0000-0000000000a1")
AGENT_ID = UUID("00000000-0000-0000-0000-0000000000aa")
OTHER_AGENT = UUID("00000000-0000-0000-0000-0000000000ab")
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
HOTEL_ID = UUID("00000000-0000-0000-0000-0000000000b1")
WALK_ID = UUID("00000000-0000-0000-0000-0000000000b2")
TRIP = TripBrief(
    WISH_ID,
    "Ten of us, a week of hiking",
    "Greece",
    "Chania",
    Decimal("9000.00"),
    "EUR",
    10,
    date(2026, 6, 1),
    date(2026, 6, 4),  # 4 days, nights 1 to 3
)
FITTING = [
    OfferSummary(HOTEL_ID, "hotel", "Mountain lodge", "", (), False, frozenset({1, 2, 3})),
    OfferSummary(WALK_ID, "activity", "Gorge walk", "", (), False, frozenset({2})),
]


def taken_custom_plan() -> Plan:
    plan = Plan.custom_request(WISH_ID, True, "A custom request", None, NOW)
    plan.take(AGENT_ID, NOW)
    return plan


class FakePlans:
    def __init__(self, plan: Plan) -> None:
        self.plan = plan
        self.added: list[UUID] = []

    async def get(self, plan_id: UUID) -> Plan | None:
        return self.plan if self.plan.id == plan_id else None

    async def add_item(self, plan: Plan, item_id: UUID) -> None:
        self.added.append(item_id)
        self.plan = plan


class FakeCatalog:
    def __init__(self) -> None:
        self.fitting_calls: list[tuple] = []

    async def fitting_offers(self, country, city, tags, persons, start, end):
        self.fitting_calls.append((country, city, tuple(tags), persons, start, end))
        return FITTING

    async def contacts_for(self, offer_ids):
        return [
            OfferContact(
                offer.id, offer.kind, offer.title, "", f"{offer.title} SARL", "a@b.c", None
            )
            for offer in FITTING
            if offer.id in offer_ids
        ]


class FakeTrips:
    def __init__(self, trip: TripBrief | None = TRIP) -> None:
        self.trip = trip

    async def for_wish_ids(self, wish_ids):
        return {WISH_ID: self.trip} if self.trip else {}


class FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FixedClock:
    def now(self) -> datetime:
        return LATER


async def test_the_offers_fit_the_trip_with_their_partner_and_open_days():
    plan = taken_custom_plan()
    catalog = FakeCatalog()

    offers = await ListPlanOffers(FakePlans(plan), catalog, FakeTrips())(plan.id, AGENT_ID)

    assert [(o.id, o.partner_name, o.open_days) for o in offers] == [
        (HOTEL_ID, "Mountain lodge SARL", (1, 2, 3)),
        (WALK_ID, "Gorge walk SARL", (2,)),
    ]
    # The trip's own group and dates, no tag: the agent sees every fitting offer.
    assert catalog.fitting_calls == [
        ("Greece", "Chania", (), 10, date(2026, 6, 1), date(2026, 6, 4))
    ]


async def test_another_agent_does_not_see_the_offers():
    plan = taken_custom_plan()

    with pytest.raises(PermissionDenied):
        await ListPlanOffers(FakePlans(plan), FakeCatalog(), FakeTrips())(plan.id, OTHER_AGENT)


async def test_a_trip_without_dates_has_no_offers():
    plan = taken_custom_plan()
    trips = FakeTrips(None)

    assert await ListPlanOffers(FakePlans(plan), FakeCatalog(), trips)(plan.id, AGENT_ID) == []


def add_item(plan: Plan) -> tuple[AddPlanItem, FakePlans, FakeUow]:
    plans, uow = FakePlans(plan), FakeUow()
    return AddPlanItem(plans, FakeCatalog(), FakeTrips(), uow, FixedClock()), plans, uow


def command(plan: Plan, offer_id: UUID, day: int, quantity: int = 1, agent=AGENT_ID):
    return AddItemCommand(plan.id, agent, offer_id, day, quantity, None)


async def test_the_agent_adds_a_hotel_and_an_activity_and_gets_the_plan_back():
    plan = taken_custom_plan()
    use_case, plans, uow = add_item(plan)

    await use_case(command(plan, HOTEL_ID, 1, 3))
    view = await use_case(command(plan, WALK_ID, 2))

    assert [(item.offer_id, item.day, item.quantity) for item in view.items] == [
        (HOTEL_ID, 1, 3),
        (WALK_ID, 2, 1),
    ]
    assert view.items[0].partner_name == "Mountain lodge SARL"
    assert view.custom is True and view.ready_to_quote is False
    assert len(plans.added) == 2 and uow.commits == 2


async def test_an_activity_on_a_closed_day_is_refused():
    plan = taken_custom_plan()
    use_case, plans, uow = add_item(plan)

    with pytest.raises(InvalidPlan):
        await use_case(command(plan, WALK_ID, 3))
    assert plans.added == [] and uow.commits == 0


async def test_a_hotel_past_the_last_night_is_refused():
    plan = taken_custom_plan()
    use_case, plans, _ = add_item(plan)

    with pytest.raises(InvalidPlan):
        await use_case(command(plan, HOTEL_ID, 2, 3))  # nights 2, 3 and 4 of a 4-day trip
    assert plans.added == []


async def test_an_offer_that_does_not_fit_the_trip_is_refused():
    plan = taken_custom_plan()
    use_case, plans, _ = add_item(plan)

    with pytest.raises(InvalidPlan):
        await use_case(command(plan, UUID("00000000-0000-0000-0000-0000000000ff"), 1))
    assert plans.added == []


async def test_another_agent_cannot_add_and_learns_nothing_about_the_offer():
    plan = taken_custom_plan()
    use_case, plans, _ = add_item(plan)

    # 403 even for an offer that does not fit: the assignment is checked first.
    with pytest.raises(PermissionDenied):
        await use_case(command(plan, UUID(int=1), 1, agent=OTHER_AGENT))
    assert plans.added == []


async def test_no_item_is_added_once_the_quote_is_sent():
    plan = taken_custom_plan()
    item = plan.add_item(HOTEL_ID, 1, 3, None, AGENT_ID, NOW)
    plan.set_item_price(item.id, AGENT_ID, Decimal("900"), NOW)
    plan.mark_quoted(AGENT_ID, NOW)
    use_case, _, _ = add_item(plan)

    with pytest.raises(InvalidTransition):
        await use_case(command(plan, WALK_ID, 2))


async def test_an_unknown_plan_is_not_found():
    plan = taken_custom_plan()
    use_case, _, _ = add_item(plan)

    with pytest.raises(PlanNotFound):
        await use_case(AddItemCommand(UUID(int=7), AGENT_ID, WALK_ID, 2, 1, None))
