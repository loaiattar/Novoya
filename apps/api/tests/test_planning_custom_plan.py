"""Custom plans (#184): a trip no offer fits, sent to the agency, and built by its agent."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from novoya_api.planning.application.dto import PlanRequest
from novoya_api.planning.application.use_cases.request_custom_plan import (
    CUSTOM_SUMMARY,
    RequestCustomPlan,
)
from novoya_api.planning.domain.errors import InvalidPlan
from novoya_api.planning.domain.plan import Plan, PlanStatus, item_fits
from novoya_api.shared.domain.errors import InvalidTransition, PermissionDenied

WISH_ID = UUID("00000000-0000-0000-0000-0000000000a1")
AGENT_ID = UUID("00000000-0000-0000-0000-0000000000aa")
OTHER_AGENT = UUID("00000000-0000-0000-0000-0000000000ab")
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
REQUEST = PlanRequest(
    wish_id=WISH_ID,
    text="Ten of us, a week of hiking in Crete",
    country="Greece",
    city="Chania",
    tags=("style:hiking",),
    persons=10,
    start_date=date(2026, 6, 1),
    end_date=date(2026, 6, 7),
    budget_max=Decimal("9000"),
)


def custom_plan() -> Plan:
    return Plan.custom_request(WISH_ID, True, "A custom request", "Day 1: arrive", NOW)


def taken_custom_plan() -> Plan:
    plan = custom_plan()
    plan.take(AGENT_ID, NOW)
    return plan


def test_a_custom_request_is_requested_at_once_with_no_item():
    plan = custom_plan()

    assert plan.status is PlanStatus.REQUESTED
    assert plan.custom is True
    assert plan.items == ()
    assert plan.extras == ()
    assert plan.outline == "Day 1: arrive"
    assert plan.wish_id == WISH_ID


def test_a_custom_request_cannot_be_requested_again():
    with pytest.raises(InvalidTransition):
        custom_plan().request_quote(LATER)


def test_a_plan_with_no_kept_item_is_not_ready_to_quote():
    plan = taken_custom_plan()

    assert plan.ready_to_quote() is False


def test_the_assigned_agent_adds_items_in_day_order_with_no_price():
    plan = taken_custom_plan()
    offer_a, offer_b = uuid4(), uuid4()

    later = plan.add_item(offer_a, 3, 1, "Gorge walk", AGENT_ID, LATER)
    earlier = plan.add_item(offer_b, 1, 2, None, AGENT_ID, LATER)

    assert [item.id for item in plan.items] == [earlier.id, later.id]
    assert later.negotiated_price is None and later.removed is False
    assert later.note == "Gorge walk"
    assert plan.updated_at == LATER
    assert plan.ready_to_quote() is False  # added, not priced yet


def test_an_added_item_once_priced_makes_the_plan_ready():
    plan = taken_custom_plan()
    item = plan.add_item(uuid4(), 1, 1, None, AGENT_ID, LATER)

    plan.set_item_price(item.id, AGENT_ID, Decimal("120"), LATER)

    assert plan.ready_to_quote() is True


def test_another_agent_cannot_add_an_item():
    with pytest.raises(PermissionDenied):
        taken_custom_plan().add_item(uuid4(), 1, 1, None, OTHER_AGENT, LATER)


def test_no_item_is_added_before_the_plan_is_taken():
    with pytest.raises(InvalidTransition):
        custom_plan().add_item(uuid4(), 1, 1, None, AGENT_ID, LATER)


@pytest.mark.parametrize(("day", "quantity"), [(0, 1), (1, 0)])
def test_an_item_needs_a_day_and_a_quantity(day, quantity):
    with pytest.raises(InvalidPlan):
        taken_custom_plan().add_item(uuid4(), day, quantity, None, AGENT_ID, LATER)


@pytest.mark.parametrize(
    ("is_hotel", "day", "quantity", "open_days", "trip_days", "fits"),
    [
        (False, 2, 1, frozenset({2}), 3, True),
        (False, 2, 1, frozenset({1, 3}), 3, False),  # closed that day
        (False, 4, 1, frozenset({4}), 3, False),  # after the trip
        (True, 1, 2, frozenset({1, 2}), 3, True),  # nights 1 and 2 of a 3-day trip
        (True, 1, 3, frozenset({1, 2, 3}), 3, False),  # a third night past the last day
        (True, 1, 2, frozenset({1}), 3, False),  # closed on the second night
        (True, 1, 1, frozenset({1}), 1, True),  # a one-day trip still has its night
    ],
)
def test_item_fits_the_trip_and_the_offer_s_open_days(
    is_hotel, day, quantity, open_days, trip_days, fits
):
    assert item_fits(is_hotel, day, quantity, open_days, trip_days) is fits


class FakeWriter:
    def __init__(self, events: list[str], outline: str | None) -> None:
        self.events = events
        self.outline = outline

    async def write(self, request: PlanRequest) -> str | None:
        self.events.append("write")
        return self.outline


class FakePlans:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.added: list[Plan] = []

    async def add(self, plan: Plan) -> None:
        self.events.append("add")
        self.added.append(plan)


class FakeUow:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def commit(self) -> None:
        self.events.append("commit")

    async def rollback(self) -> None:
        self.events.append("rollback")


class FixedClock:
    def now(self) -> datetime:
        return NOW


async def test_the_custom_plan_keeps_the_outline_for_the_agent_and_no_item():
    events: list[str] = []
    plans = FakePlans(events)
    use_case = RequestCustomPlan(
        FakeWriter(events, "Day 1: Chania old town"), plans, FakeUow(events), FixedClock()
    )

    view = await use_case(REQUEST)

    # The read ends before the model writes; the caller commits.
    assert events == ["rollback", "write", "add"]
    [plan] = plans.added
    assert plan.custom is True and plan.status is PlanStatus.REQUESTED
    assert plan.outline == "Day 1: Chania old town"
    assert plan.summary == CUSTOM_SUMMARY
    assert plan.based_on_preferences is True
    # The client's view has no outline at all.
    assert view.custom is True and view.items == () and view.status == "requested"
    assert not hasattr(view, "outline")


async def test_the_custom_plan_is_sent_without_an_outline_when_the_model_fails():
    events: list[str] = []
    plans = FakePlans(events)
    use_case = RequestCustomPlan(FakeWriter(events, None), plans, FakeUow(events), FixedClock())

    await use_case(REQUEST)

    assert plans.added[0].outline is None
