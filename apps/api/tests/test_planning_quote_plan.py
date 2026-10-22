"""Plan.mark_quoted, the answer after it, and the QuotePlan, RecordAnswer and GetPricedPlan
use cases, tested with fake ports: no database."""

from dataclasses import fields
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from novoya_api.planning.application.dto import (
    OfferSummary,
    PricedExtra,
    PricedItem,
    PricedPlan,
    TripBrief,
)
from novoya_api.planning.application.use_cases.get_priced_plan import GetPricedPlan
from novoya_api.planning.application.use_cases.quote_plan import QuotePlan
from novoya_api.planning.application.use_cases.record_answer import RecordAnswer
from novoya_api.planning.domain.errors import PlanNotFound, PlanNotReady
from novoya_api.planning.domain.plan import DraftItem, Plan, PlanExtra, PlanStatus
from novoya_api.shared.domain.errors import InvalidInput, InvalidTransition, PermissionDenied

WISH_ID = UUID("00000000-0000-0000-0000-0000000000a1")
CLIENT_ID = UUID("00000000-0000-0000-0000-000000000001")
AGENT_ID = UUID("00000000-0000-0000-0000-0000000000aa")
OTHER_AGENT = UUID("00000000-0000-0000-0000-0000000000ab")
HOTEL_ID = UUID("00000000-0000-0000-0000-0000000000b1")
BOAT_ID = UUID("00000000-0000-0000-0000-0000000000b2")
GUIDE_ID = UUID("00000000-0000-0000-0000-0000000000c1")
BREAKFAST_ID = UUID("00000000-0000-0000-0000-0000000000c2")
TRANSFER_ID = UUID("00000000-0000-0000-0000-0000000000c3")
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
HOTEL = OfferSummary(HOTEL_ID, "hotel", "Sea view room", "Rooms over the bay", (), False)
BOAT = OfferSummary(BOAT_ID, "activity", "Boat trip", "A day at sea", (), False)
TRIP = TripBrief(
    WISH_ID,
    "A week in Chania",
    "Greece",
    "Chania",
    Decimal("1500.00"),
    "EUR",
    2,
    date(2026, 5, 10),
    date(2026, 5, 17),
    tags=("style:beach", "food:seafood"),
)
GUIDE = PlanExtra(GUIDE_ID, "on_quote", None, label="Private guide", unit="per activity")
BREAKFAST = PlanExtra(BREAKFAST_ID, "included", None, label="Breakfast", unit="")
TRANSFER = PlanExtra(
    TRANSFER_ID, "supplement", Decimal("25"), label="Airport transfer", unit="per trip"
)


def negotiating_plan(extras: tuple[PlanExtra, ...] = ()) -> Plan:
    plan = Plan.propose(
        WISH_ID,
        True,
        "A week by the sea",
        [DraftItem(HOTEL_ID, 1, 6, None), DraftItem(BOAT_ID, 3, 2, "Bring a hat")],
        8,
        NOW,
    )
    plan.request_quote(NOW, extras)
    plan.take(AGENT_ID, NOW)
    return plan


def priced_plan(extras: tuple[PlanExtra, ...] = ()) -> Plan:
    plan = negotiating_plan(extras)
    plan.set_item_price(plan.items[0].id, AGENT_ID, Decimal("900.00"), NOW)
    plan.set_item_price(plan.items[1].id, AGENT_ID, Decimal("120.00"), NOW)
    return plan


class FakePlans:
    def __init__(self, plan: Plan | None) -> None:
        self.plan = plan
        self.saved: list[Plan] = []

    async def get(self, plan_id: UUID) -> Plan | None:
        if self.plan is None or self.plan.id != plan_id:
            return None
        return self.plan

    async def save(self, plan: Plan) -> None:
        self.saved.append(plan)


class FakeCatalog:
    async def summaries_for(self, offer_ids: list[UUID]) -> list[OfferSummary]:
        return [offer for offer in (HOTEL, BOAT) if offer.id in offer_ids]


class FakeTrips:
    async def for_wish_ids(self, wish_ids: list[UUID]) -> dict[UUID, TripBrief]:
        return {WISH_ID: TRIP} if WISH_ID in wish_ids else {}


class FakeWishes:
    async def owner_id(self, wish_id: UUID) -> UUID | None:
        return CLIENT_ID if wish_id == WISH_ID else None


class FixedClock:
    def now(self) -> datetime:
        return LATER


def quote_plan(plan: Plan | None) -> tuple[QuotePlan, FakePlans]:
    plans = FakePlans(plan)
    return QuotePlan(plans, FakeCatalog(), FakeTrips(), FakeWishes(), FixedClock()), plans


# Plan.mark_quoted


def test_a_fully_priced_plan_is_marked_quoted():
    plan = priced_plan()

    plan.mark_quoted(AGENT_ID, LATER)

    assert plan.status is PlanStatus.QUOTED
    assert plan.updated_at == LATER


def test_a_plan_not_being_negotiated_cannot_be_quoted():
    plan = Plan.propose(WISH_ID, True, "Sun", [DraftItem(HOTEL_ID, 1, 2, None)], 3, NOW)
    plan.request_quote(NOW)

    with pytest.raises(InvalidTransition):
        plan.mark_quoted(AGENT_ID, LATER)


def test_a_quoted_plan_cannot_be_quoted_again():
    plan = priced_plan()
    plan.mark_quoted(AGENT_ID, LATER)

    with pytest.raises(InvalidTransition):
        plan.mark_quoted(AGENT_ID, LATER)


def test_another_agent_cannot_quote_the_plan():
    plan = priced_plan()

    with pytest.raises(PermissionDenied):
        plan.mark_quoted(OTHER_AGENT, LATER)

    assert plan.status is PlanStatus.NEGOTIATING


def test_a_kept_item_without_a_price_blocks_the_quote():
    plan = negotiating_plan()
    plan.set_item_price(plan.items[0].id, AGENT_ID, Decimal("900.00"), NOW)

    with pytest.raises(PlanNotReady):
        plan.mark_quoted(AGENT_ID, LATER)

    assert plan.status is PlanStatus.NEGOTIATING


def test_an_unpriced_on_quote_extra_blocks_the_quote():
    plan = priced_plan((GUIDE,))

    with pytest.raises(PlanNotReady):
        plan.mark_quoted(AGENT_ID, LATER)


def test_an_unconfirmed_per_person_supplement_blocks_the_quote():
    per_person = PlanExtra(
        TRANSFER_ID, "supplement", Decimal("25"), label="Dinner", unit="per person"
    )
    plan = priced_plan((per_person,))

    with pytest.raises(PlanNotReady):
        plan.mark_quoted(AGENT_ID, LATER)


def test_a_removed_item_without_a_price_does_not_block_the_quote():
    plan = negotiating_plan()
    plan.set_item_price(plan.items[0].id, AGENT_ID, Decimal("900.00"), NOW)
    plan.remove_item(plan.items[1].id, AGENT_ID, NOW)

    plan.mark_quoted(AGENT_ID, LATER)

    assert plan.status is PlanStatus.QUOTED


def test_plan_not_ready_is_an_invalid_input_with_its_own_code():
    assert issubclass(PlanNotReady, InvalidInput)
    assert PlanNotReady.code == "plan_not_ready"


# QuotePlan


async def test_quoting_marks_the_plan_quoted_and_saves_it():
    plan = priced_plan()
    use_case, plans = quote_plan(plan)

    await use_case(plan.id, AGENT_ID)

    assert plans.saved == [plan]
    assert plan.status is PlanStatus.QUOTED
    assert plan.updated_at == LATER


async def test_the_priced_plan_lists_kept_items_with_titles_and_prices():
    plan = priced_plan()
    use_case, _plans = quote_plan(plan)

    priced = await use_case(plan.id, AGENT_ID)

    assert priced.items == (
        PricedItem(1, "hotel", "Sea view room", "Rooms over the bay", 6, Decimal("900.00")),
        PricedItem(3, "activity", "Boat trip", "A day at sea", 2, Decimal("120.00")),
    )


async def test_the_priced_plan_leaves_removed_items_out():
    plan = priced_plan()
    plan.remove_item(plan.items[1].id, AGENT_ID, NOW)
    use_case, _plans = quote_plan(plan)

    priced = await use_case(plan.id, AGENT_ID)

    assert [item.title for item in priced.items] == ["Sea view room"]
    assert priced.total == Decimal("900.00")


async def test_the_priced_plan_sorts_items_by_day():
    plan = priced_plan()
    plan.items = (plan.items[1], plan.items[0])
    use_case, _plans = quote_plan(plan)

    priced = await use_case(plan.id, AGENT_ID)

    assert [item.day for item in priced.items] == [1, 3]


async def test_the_priced_plan_has_the_extras_and_no_price_for_an_included_one():
    plan = priced_plan((GUIDE, BREAKFAST, TRANSFER))
    plan.set_extra_price(GUIDE_ID, AGENT_ID, Decimal("45.00"), NOW)
    use_case, _plans = quote_plan(plan)

    priced = await use_case(plan.id, AGENT_ID)

    assert priced.extras == (
        PricedExtra("Private guide", "per activity", "on_quote", Decimal("45.00")),
        PricedExtra("Breakfast", "", "included", None),
        PricedExtra("Airport transfer", "per trip", "supplement", Decimal("25")),
    )


async def test_the_total_is_the_plans_priced_total():
    plan = priced_plan((GUIDE, BREAKFAST, TRANSFER))
    plan.set_extra_price(GUIDE_ID, AGENT_ID, Decimal("45.00"), NOW)
    use_case, _plans = quote_plan(plan)

    priced = await use_case(plan.id, AGENT_ID)

    assert priced.total == Decimal("1090.00")


async def test_the_priced_plan_names_the_client_and_the_agent():
    plan = priced_plan()
    use_case, _plans = quote_plan(plan)

    priced = await use_case(plan.id, AGENT_ID)

    assert (priced.plan_id, priced.wish_id) == (plan.id, WISH_ID)
    assert priced.client_id == CLIENT_ID
    assert priced.agent_id == AGENT_ID
    assert priced.summary == "A week by the sea"


async def test_the_priced_plan_carries_the_trip_and_its_tags():
    plan = priced_plan()
    use_case, _plans = quote_plan(plan)

    priced = await use_case(plan.id, AGENT_ID)

    assert priced.wish_text == "A week in Chania"
    assert (priced.country, priced.city) == ("Greece", "Chania")
    assert priced.persons == 2
    assert (priced.start_date, priced.end_date) == (date(2026, 5, 10), date(2026, 5, 17))
    assert (priced.budget_max, priced.currency) == (Decimal("1500.00"), "EUR")
    assert priced.tags == ("style:beach", "food:seafood")


async def test_quoting_a_missing_plan_is_not_found():
    use_case, plans = quote_plan(priced_plan())

    with pytest.raises(PlanNotFound):
        await use_case(UUID("00000000-0000-0000-0000-0000000000ff"), AGENT_ID)

    assert plans.saved == []


async def test_quoting_a_plan_that_is_not_ready_saves_nothing():
    plan = negotiating_plan()
    use_case, plans = quote_plan(plan)

    with pytest.raises(PlanNotReady):
        await use_case(plan.id, AGENT_ID)

    assert plans.saved == []
    assert plan.status is PlanStatus.NEGOTIATING


def test_the_priced_plan_never_has_a_partner_field():
    models = (PricedPlan, PricedItem, PricedExtra)
    names = {field.name for model in models for field in fields(model)}

    assert not any("partner" in name for name in names)


def test_a_trip_brief_has_no_tags_by_default():
    brief = TripBrief(WISH_ID, "Somewhere", None, None, None, None, None, None, None)

    assert brief.tags == ()


class PricedMeanwhile(FakePlans):
    """The second read sees a price edit that landed between get() and save()."""

    def __init__(self, plan: Plan, meanwhile: Plan) -> None:
        super().__init__(plan)
        self.meanwhile = meanwhile
        self.reads = 0

    async def get(self, plan_id: UUID) -> Plan | None:
        self.reads += 1
        return self.plan if self.reads == 1 else self.meanwhile


async def test_the_quote_uses_the_prices_read_after_the_plan_is_locked():
    plan = priced_plan()
    meanwhile = priced_plan()
    meanwhile.id = plan.id
    meanwhile.set_item_price(meanwhile.items[0].id, AGENT_ID, Decimal("950.00"), NOW)
    plans = PricedMeanwhile(plan, meanwhile)
    use_case = QuotePlan(plans, FakeCatalog(), FakeTrips(), FakeWishes(), FixedClock())

    priced = await use_case(plan.id, AGENT_ID)

    assert priced.total == Decimal("1070.00")


async def test_an_item_put_back_meanwhile_without_a_price_stops_the_quote():
    plan = priced_plan()
    meanwhile = negotiating_plan()  # no prices: as if an item came back unpriced
    meanwhile.id = plan.id
    plans = PricedMeanwhile(plan, meanwhile)
    use_case = QuotePlan(plans, FakeCatalog(), FakeTrips(), FakeWishes(), FixedClock())

    with pytest.raises(PlanNotReady):
        await use_case(plan.id, AGENT_ID)


# Plan.record_answer, RecordAnswer and GetPricedPlan: after the quote


def quoted_plan() -> Plan:
    plan = priced_plan()
    plan.mark_quoted(AGENT_ID, NOW)
    return plan


@pytest.mark.parametrize(
    ("accepted", "status"), [(True, PlanStatus.ACCEPTED), (False, PlanStatus.REJECTED)]
)
def test_the_answer_moves_a_quoted_plan(accepted, status):
    plan = quoted_plan()

    plan.record_answer(accepted, LATER)

    assert plan.status is status
    assert plan.updated_at == LATER
    assert plan.is_quoted()


def test_a_plan_not_quoted_cannot_be_answered():
    with pytest.raises(InvalidTransition):
        priced_plan().record_answer(True, LATER)


def test_an_answered_plan_cannot_be_answered_again():
    plan = quoted_plan()
    plan.record_answer(False, LATER)

    with pytest.raises(InvalidTransition):
        plan.record_answer(True, LATER)


async def test_record_answer_saves_the_plan():
    plans = FakePlans(quoted_plan())

    await RecordAnswer(plans, FixedClock())(plans.plan.id, accepted=True)

    assert [plan.status for plan in plans.saved] == [PlanStatus.ACCEPTED]


async def test_record_answer_for_a_missing_plan_is_not_found():
    with pytest.raises(PlanNotFound):
        await RecordAnswer(FakePlans(None), FixedClock())(WISH_ID, accepted=True)


def get_priced_plan(plan: Plan | None) -> GetPricedPlan:
    return GetPricedPlan(FakePlans(plan), FakeCatalog(), FakeTrips(), FakeWishes())


async def test_get_priced_plan_reads_a_quoted_plan_like_its_quote():
    plan = quoted_plan()

    priced = await get_priced_plan(plan)(plan.id)

    assert priced is not None
    assert (priced.client_id, priced.agent_id) == (CLIENT_ID, AGENT_ID)
    assert [(item.title, item.price) for item in priced.items] == [
        ("Sea view room", Decimal("900.00")),
        ("Boat trip", Decimal("120.00")),
    ]
    assert priced.total == Decimal("1020.00")
    assert (priced.city, priced.persons, priced.budget_max) == ("Chania", 2, Decimal("1500.00"))


async def test_get_priced_plan_reads_an_answered_plan():
    plan = quoted_plan()
    plan.record_answer(True, LATER)

    assert await get_priced_plan(plan)(plan.id) is not None


async def test_get_priced_plan_is_none_before_the_quote():
    plan = priced_plan()

    assert await get_priced_plan(plan)(plan.id) is None


async def test_get_priced_plan_is_none_for_a_missing_plan():
    assert await get_priced_plan(None)(WISH_ID) is None
