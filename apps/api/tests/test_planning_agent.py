"""ListQuoteQueue, TakePlan and SetItemPrice are tested with fake ports: no database."""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from novoya_api.planning.application.dto import OfferContact, TripBrief
from novoya_api.planning.application.use_cases.get_agent_plan import GetAgentPlan
from novoya_api.planning.application.use_cases.list_quote_queue import ListQuoteQueue
from novoya_api.planning.application.use_cases.set_item_price import SetItemCommand, SetItemPrice
from novoya_api.planning.application.use_cases.take_plan import TakePlan
from novoya_api.planning.domain.errors import PlanNotFound
from novoya_api.planning.domain.plan import DraftItem, Plan, PlanStatus
from novoya_api.shared.domain.errors import InvalidTransition, PermissionDenied

WISH_ID = UUID("00000000-0000-0000-0000-0000000000a1")
OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")
AGENT_ID = UUID("00000000-0000-0000-0000-0000000000aa")
OTHER_AGENT = UUID("00000000-0000-0000-0000-0000000000ab")
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
HOTEL_ID = UUID("00000000-0000-0000-0000-0000000000b1")
HOTEL = OfferContact(
    HOTEL_ID,
    "hotel",
    "Sea view hotel",
    "Rooms over the bay",
    "Elounda Bay House",
    "stay@elounda.example",
    "+30 28210 00001",
)
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
)


def stored_plan() -> Plan:
    plan = Plan.propose(
        WISH_ID, True, "A week by the sea", [DraftItem(HOTEL_ID, 1, 2, None)], 3, NOW
    )
    plan.request_quote(NOW)
    return plan


class FakePlans:
    def __init__(self, plan: Plan | None = None, *others: Plan) -> None:
        self.plan = plan
        self.others = others
        self.queue_calls: list[tuple[set[PlanStatus], UUID, int, int]] = []

    async def get(self, plan_id: UUID) -> Plan | None:
        if self.plan is None or self.plan.id != plan_id:
            return None
        return self.plan

    async def list_queue(
        self, statuses: Sequence[PlanStatus], agent_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Plan]:
        """Requested plans of everyone, the other statuses only when assigned to agent_id."""
        self.queue_calls.append((set(statuses), agent_id, limit, offset))
        stored = [plan for plan in (self.plan, *self.others) if plan is not None]
        found = [
            plan
            for plan in stored
            if plan.status in statuses
            and (plan.status is PlanStatus.REQUESTED or plan.assigned_agent_id == agent_id)
        ]
        return sorted(found, key=lambda plan: (plan.updated_at, plan.id))[offset : offset + limit]

    async def save(self, plan: Plan) -> None:
        self.plan = plan

    async def save_item(self, plan: Plan, item_id: UUID, write) -> None:
        self.plan = plan


class FakeCatalog:
    async def contacts_for(self, offer_ids: list[UUID]) -> list[OfferContact]:
        return [HOTEL] if HOTEL_ID in offer_ids else []


class FakeTrips:
    def __init__(self, briefs: dict[UUID, TripBrief] | None = None) -> None:
        self.briefs = {WISH_ID: TRIP} if briefs is None else briefs

    async def for_wish_ids(self, wish_ids: list[UUID]) -> dict[UUID, TripBrief]:
        return {wish_id: self.briefs[wish_id] for wish_id in wish_ids if wish_id in self.briefs}


class FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None: ...


class FixedClock:
    def now(self) -> datetime:
        return LATER


def take_plan(plan: Plan | None) -> tuple[TakePlan, FakeUow]:
    uow = FakeUow()
    return (
        TakePlan(FakePlans(plan), FakeCatalog(), FakeTrips(), uow, FixedClock()),
        uow,
    )


async def test_the_queue_lists_requested_plans_with_the_wish():
    plan = stored_plan()
    entries = await ListQuoteQueue(FakePlans(plan), FakeTrips())(AGENT_ID, [PlanStatus.REQUESTED])

    assert len(entries) == 1
    assert entries[0].id == plan.id
    assert entries[0].wish_text == "A week in Chania"
    assert entries[0].country == "Greece"
    assert entries[0].city == "Chania"
    assert entries[0].persons == 2
    assert entries[0].budget_max == Decimal("1500.00")
    assert entries[0].start_date == date(2026, 5, 10)


async def test_the_queue_is_empty_when_nothing_is_requested():
    plan = stored_plan()
    plan.take(AGENT_ID, LATER)
    assert await ListQuoteQueue(FakePlans(plan), FakeTrips())(AGENT_ID) == []


async def test_the_queue_asks_for_requested_plans_by_default():
    plans = FakePlans(stored_plan())

    await ListQuoteQueue(plans, FakeTrips())(AGENT_ID)

    assert plans.queue_calls == [({PlanStatus.REQUESTED}, AGENT_ID, 50, 0)]


async def test_the_queue_passes_the_statuses_and_the_caller_to_the_repository():
    plans = FakePlans(stored_plan())

    await ListQuoteQueue(plans, FakeTrips())(
        AGENT_ID, [PlanStatus.QUOTED, PlanStatus.ACCEPTED], limit=10, offset=20
    )

    assert plans.queue_calls == [({PlanStatus.QUOTED, PlanStatus.ACCEPTED}, AGENT_ID, 10, 20)]


async def test_the_queue_lists_my_negotiating_plans_with_the_wish():
    plan = stored_plan()
    plan.take(AGENT_ID, LATER)

    entries = await ListQuoteQueue(FakePlans(plan), FakeTrips())(AGENT_ID, [PlanStatus.NEGOTIATING])

    assert [entry.id for entry in entries] == [plan.id]
    assert entries[0].status == PlanStatus.NEGOTIATING
    assert entries[0].wish_text == "A week in Chania"


async def test_the_queue_never_lists_another_agents_negotiating_plan():
    plan = stored_plan()
    plan.take(OTHER_AGENT, LATER)

    entries = await ListQuoteQueue(FakePlans(plan), FakeTrips())(
        AGENT_ID, [PlanStatus.REQUESTED, PlanStatus.NEGOTIATING]
    )

    assert entries == []


async def test_an_agent_takes_a_requested_plan():
    plan = stored_plan()
    use_case, uow = take_plan(plan)

    view = await use_case(plan.id, AGENT_ID)

    assert view.status == "negotiating"
    assert view.assigned_agent_id == AGENT_ID
    assert view.items[0].partner_name == "Elounda Bay House"
    assert view.items[0].partner_contact_phone == "+30 28210 00001"
    assert view.total == Decimal("0")
    assert view.over_budget is False
    assert view.budget_max == Decimal("1500.00")
    assert plan.status is PlanStatus.NEGOTIATING
    assert uow.commits == 1


async def test_taking_a_missing_plan_is_not_found():
    use_case, uow = take_plan(stored_plan())
    with pytest.raises(PlanNotFound):
        await use_case(UUID("00000000-0000-0000-0000-0000000000ff"), AGENT_ID)
    assert uow.commits == 0


async def test_taking_an_already_taken_plan_is_an_invalid_transition():
    plan = stored_plan()
    plan.take(AGENT_ID, LATER)
    use_case, uow = take_plan(plan)
    with pytest.raises(InvalidTransition):
        await use_case(plan.id, OTHER_AGENT)
    assert uow.commits == 0


async def test_the_assigned_agent_reads_the_plan_with_partners():
    plan = stored_plan()
    plan.take(AGENT_ID, LATER)
    view = await GetAgentPlan(FakePlans(plan), FakeCatalog(), FakeTrips())(plan.id, AGENT_ID)
    assert view.items[0].partner_name == "Elounda Bay House"
    assert view.items[0].negotiated_price is None


async def test_another_agent_cannot_read_a_taken_plan():
    plan = stored_plan()
    plan.take(AGENT_ID, LATER)
    with pytest.raises(PermissionDenied):
        await GetAgentPlan(FakePlans(plan), FakeCatalog(), FakeTrips())(plan.id, OTHER_AGENT)


def set_item(plan: Plan) -> tuple[SetItemPrice, FakeUow]:
    uow = FakeUow()
    return (
        SetItemPrice(FakePlans(plan), FakeCatalog(), FakeTrips(), uow, FixedClock()),
        uow,
    )


async def test_the_assigned_agent_sets_a_price():
    plan = stored_plan()
    plan.take(AGENT_ID, NOW)
    use_case, uow = set_item(plan)

    view = await use_case(
        SetItemCommand(plan.id, plan.items[0].id, AGENT_ID, Decimal("120.00"), None)
    )

    assert view.items[0].negotiated_price == Decimal("120.00")
    assert view.total == Decimal("120.00")
    assert view.over_budget is False
    assert uow.commits == 1


async def test_a_total_above_budget_is_flagged():
    plan = stored_plan()
    plan.take(AGENT_ID, NOW)
    use_case, _uow = set_item(plan)

    view = await use_case(
        SetItemCommand(plan.id, plan.items[0].id, AGENT_ID, Decimal("2000.00"), None)
    )

    assert view.over_budget is True
    assert view.total == Decimal("2000.00")


async def test_over_budget_is_false_when_the_wish_has_no_budget():
    plan = stored_plan()
    plan.take(AGENT_ID, NOW)
    brief = TripBrief(
        WISH_ID,
        "A week in Chania",
        "Greece",
        "Chania",
        None,
        None,
        2,
        date(2026, 5, 10),
        date(2026, 5, 17),
    )
    uow = FakeUow()
    view = await SetItemPrice(
        FakePlans(plan), FakeCatalog(), FakeTrips({WISH_ID: brief}), uow, FixedClock()
    )(SetItemCommand(plan.id, plan.items[0].id, AGENT_ID, Decimal("2000.00"), None))

    assert view.budget_max is None
    assert view.over_budget is False


async def test_the_assigned_agent_removes_an_item():
    plan = Plan.propose(
        WISH_ID,
        True,
        "Sun and sea",
        [DraftItem(HOTEL_ID, 1, 2, None), DraftItem(HOTEL_ID, 3, 1, "Boat")],
        4,
        NOW,
    )
    plan.request_quote(NOW)
    plan.take(AGENT_ID, NOW)
    use_case, uow = set_item(plan)

    view = await use_case(SetItemCommand(plan.id, plan.items[1].id, AGENT_ID, None, True))

    assert view.items[1].removed is True
    assert uow.commits == 1


async def test_the_assigned_agent_restores_a_removed_item():
    plan = Plan.propose(
        WISH_ID,
        True,
        "Sun and sea",
        [DraftItem(HOTEL_ID, 1, 2, None), DraftItem(HOTEL_ID, 3, 1, "Boat")],
        4,
        NOW,
    )
    plan.request_quote(NOW)
    plan.take(AGENT_ID, NOW)
    plan.remove_item(plan.items[1].id, AGENT_ID, NOW)
    use_case, uow = set_item(plan)

    view = await use_case(SetItemCommand(plan.id, plan.items[1].id, AGENT_ID, None, False))

    assert view.items[1].removed is False
    assert view.items[1].negotiated_price is None
    assert uow.commits == 1


async def test_another_agent_cannot_set_a_price():
    plan = stored_plan()
    plan.take(AGENT_ID, NOW)
    use_case, uow = set_item(plan)
    with pytest.raises(PermissionDenied):
        await use_case(
            SetItemCommand(plan.id, plan.items[0].id, OTHER_AGENT, Decimal("10.00"), None)
        )
    assert uow.commits == 0
