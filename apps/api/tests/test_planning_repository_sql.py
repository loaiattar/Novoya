"""The plans repository against a real PostgreSQL: a plan reads back as it was added.

Uses the database fixture of test_catalog_sql.py: skipped when Postgres does not answer.
"""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from novoya_api.accounts.infrastructure.db.models import UserModel
from novoya_api.catalog.infrastructure.db.models import ExtraRow, OfferRow, PartnerRow
from novoya_api.planning.application.ports.plan_repository import ItemWrite
from novoya_api.planning.application.use_cases.set_item_price import SetItemCommand, SetItemPrice
from novoya_api.planning.application.use_cases.take_plan import TakePlan
from novoya_api.planning.domain.errors import InvalidPlan
from novoya_api.planning.domain.plan import DraftItem, Plan, PlanExtra, PlanItem, PlanStatus
from novoya_api.planning.infrastructure.db.repository import SqlPlanRepository
from novoya_api.shared.domain.errors import InvalidTransition
from novoya_api.wishes.domain.wish import Wish
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)


@pytest.fixture
async def engine(database_url) -> AsyncIterator[AsyncEngine]:  # noqa: F811
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE plan_extras, plan_items, plans, wishes, extras, offers, partners CASCADE"
            )
        )
    yield engine
    await engine.dispose()


def new_session(engine: AsyncEngine) -> AsyncSession:
    return async_sessionmaker(engine, expire_on_commit=False)()


@pytest.fixture
async def wish_id(engine) -> UUID:
    async with new_session(engine) as session:
        user = UserModel(id=uuid4(), email=f"{uuid4()}@example.com", created_at=NOW)
        session.add(user)
        await session.flush()
        wish = Wish.create(user.id, "A week in Chania", NOW)
        await SqlWishRepository(session).add(wish)
        await session.commit()
        return wish.id


@pytest.fixture
async def offer_ids(engine) -> tuple[UUID, UUID]:
    partner = PartnerRow(
        id=uuid4(),
        name="Chania hotel",
        kind="hotel",
        country="Greece",
        city="Chania",
        contact_email="stay@example.com",
        contact_phone="+30 000",
        active=True,
    )
    offers = [
        OfferRow(
            id=uuid4(),
            partner_id=partner.id,
            kind=kind,
            title=title,
            description=title,
            country="Greece",
            city="Chania",
            min_persons=1,
            max_persons=4,
            available_from=date(2026, 4, 1),
            available_to=date(2026, 10, 31),
            tags=["style:beach"],
            featured=False,
            active=True,
        )
        for kind, title in [("hotel", "Sea view room"), ("activity", "Boat trip")]
    ]
    async with new_session(engine) as session:
        session.add(partner)
        await session.flush()
        session.add_all(offers)
        await session.commit()
    return offers[0].id, offers[1].id


async def add_plan(engine: AsyncEngine, plan: Plan) -> None:
    async with new_session(engine) as session:
        await SqlPlanRepository(session).add(plan)
        await session.commit()


async def read_plan(engine: AsyncEngine, plan_id: UUID) -> Plan | None:
    async with new_session(engine) as session:
        return await SqlPlanRepository(session).get(plan_id)


async def test_get_reads_back_a_proposed_plan_with_its_items(engine, wish_id, offer_ids):
    hotel, boat = offer_ids
    plan = Plan.propose(
        wish_id,
        True,
        "Sun and sea",
        [DraftItem(hotel, 1, 7, None), DraftItem(boat, 3, 2, "Bring a hat")],
        8,
        NOW,
    )
    await add_plan(engine, plan)

    read = await read_plan(engine, plan.id)

    assert read == plan
    assert read.status is PlanStatus.PROPOSED
    assert all(item.negotiated_price is None for item in read.items)
    assert all(item.removed is False for item in read.items)


async def test_get_returns_the_items_ordered_by_day(engine, wish_id, offer_ids):
    hotel, boat = offer_ids
    late = PlanItem(uuid4(), boat, 5, 1, None)
    early = PlanItem(uuid4(), hotel, 1, 7, None)
    plan = Plan(
        id=uuid4(),
        wish_id=wish_id,
        status=PlanStatus.PROPOSED,
        based_on_preferences=False,
        summary="Unordered",
        items=(late, early),
        created_at=NOW,
        updated_at=NOW,
    )
    await add_plan(engine, plan)

    read = await read_plan(engine, plan.id)

    assert read == replace(plan, items=(early, late))


async def test_get_returns_none_for_an_unknown_plan(engine):
    assert await read_plan(engine, uuid4()) is None


async def test_save_writes_requested_status(engine, wish_id, offer_ids):
    hotel, _boat = offer_ids
    later = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    plan = Plan.propose(wish_id, True, "Sun and sea", [DraftItem(hotel, 1, 7, None)], 8, NOW)
    await add_plan(engine, plan)

    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        loaded = await repo.get(plan.id)
        loaded.request_quote(later)
        await repo.save(loaded)
        await session.commit()

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert read.status is PlanStatus.REQUESTED
    assert read.updated_at == later
    assert all(item.negotiated_price is None for item in read.items)


async def test_save_does_not_overwrite_item_prices(engine, wish_id, offer_ids):
    hotel, _boat = offer_ids
    plan = Plan.propose(wish_id, True, "Sun and sea", [DraftItem(hotel, 1, 7, None)], 8, NOW)
    await add_plan(engine, plan)

    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        loaded = await repo.get(plan.id)
        loaded.items = (replace(loaded.items[0], negotiated_price=Decimal("120.00"), removed=True),)
        await repo.save(loaded)
        await session.commit()

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert read.items[0].negotiated_price is None
    assert read.items[0].removed is False


async def test_save_item_writes_one_item_and_leaves_the_others(engine, wish_id, offer_ids):
    hotel, boat = offer_ids
    later = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    plan = Plan.propose(
        wish_id,
        True,
        "Sun and sea",
        [DraftItem(hotel, 1, 7, None), DraftItem(boat, 3, 2, None)],
        8,
        NOW,
    )
    await add_plan(engine, plan)

    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        loaded = await repo.get(plan.id)
        loaded.items = (
            replace(loaded.items[0], negotiated_price=Decimal("120.00")),
            loaded.items[1],
        )
        loaded.updated_at = later
        await repo.save_item(loaded, loaded.items[0].id, ItemWrite.PRICE)
        await session.commit()

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert read.items[0].negotiated_price == Decimal("120.00")
    assert read.items[1].negotiated_price is None
    assert read.updated_at == later


async def test_two_stale_item_saves_keep_each_price(engine, wish_id, offer_ids):
    hotel, boat = offer_ids
    later = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    agent_id = uuid4()
    plan = Plan.propose(
        wish_id,
        True,
        "Sun and sea",
        [DraftItem(hotel, 1, 7, None), DraftItem(boat, 3, 2, None)],
        8,
        NOW,
    )
    plan.request_quote(NOW)
    await add_plan(engine, plan)
    async with new_session(engine) as session:
        session.add(UserModel(id=agent_id, email=f"{agent_id}@example.com", created_at=NOW))
        await session.commit()

    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        taken = await repo.get(plan.id)
        taken.take(agent_id, later)
        await repo.save(taken)
        await session.commit()

    async with new_session(engine) as first:
        first_repo = SqlPlanRepository(first)
        tab_one = await first_repo.get(plan.id)
        async with new_session(engine) as second:
            second_repo = SqlPlanRepository(second)
            tab_two = await second_repo.get(plan.id)
            await second.commit()
            tab_two.set_item_price(tab_two.items[1].id, agent_id, Decimal("90.00"), later)
            await second_repo.save_item(tab_two, tab_two.items[1].id, ItemWrite.PRICE)
            await second.commit()
        tab_one.set_item_price(tab_one.items[0].id, agent_id, Decimal("700.00"), later)
        await first_repo.save_item(tab_one, tab_one.items[0].id, ItemWrite.PRICE)
        await first.commit()

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert read.items[0].negotiated_price == Decimal("700.00")
    assert read.items[1].negotiated_price == Decimal("90.00")


async def test_two_stale_removals_keep_one_item(engine, wish_id, offer_ids):
    hotel, boat = offer_ids
    later = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    agent_id = uuid4()
    plan = Plan.propose(
        wish_id,
        True,
        "Sun and sea",
        [DraftItem(hotel, 1, 7, None), DraftItem(boat, 3, 2, None)],
        8,
        NOW,
    )
    plan.request_quote(NOW)
    await add_plan(engine, plan)
    async with new_session(engine) as session:
        session.add(UserModel(id=agent_id, email=f"{agent_id}@example.com", created_at=NOW))
        await session.commit()

    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        taken = await repo.get(plan.id)
        taken.take(agent_id, later)
        await repo.save(taken)
        await session.commit()

    async with new_session(engine) as first:
        first_repo = SqlPlanRepository(first)
        tab_one = await first_repo.get(plan.id)
        async with new_session(engine) as second:
            second_repo = SqlPlanRepository(second)
            tab_two = await second_repo.get(plan.id)
            await second.commit()
            tab_two.remove_item(tab_two.items[1].id, agent_id, later)
            await second_repo.save_item(tab_two, tab_two.items[1].id, ItemWrite.REMOVE)
            await second.commit()
        tab_one.remove_item(tab_one.items[0].id, agent_id, later)
        with pytest.raises(InvalidPlan):
            await first_repo.save_item(tab_one, tab_one.items[0].id, ItemWrite.REMOVE)

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert sum(1 for item in read.items if not item.removed) == 1
    assert read.items[0].removed is False
    assert read.items[1].removed is True
    hotel, _boat = offer_ids
    later = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    agent_id = uuid4()
    plan = Plan.propose(wish_id, True, "Sun and sea", [DraftItem(hotel, 1, 7, None)], 8, NOW)
    await add_plan(engine, plan)
    async with new_session(engine) as session:
        session.add(UserModel(id=agent_id, email=f"{agent_id}@example.com", created_at=NOW))
        await session.commit()

    async with new_session(engine) as first:
        first_repo = SqlPlanRepository(first)
        stale = await first_repo.get(plan.id)

        async with new_session(engine) as second:
            second_repo = SqlPlanRepository(second)
            current = await second_repo.get(plan.id)
            await second.commit()
            current.request_quote(later)
            await second_repo.save(current)
            await second.commit()

        async with new_session(engine) as agent_session:
            agent_repo = SqlPlanRepository(agent_session)
            taken = await agent_repo.get(plan.id)
            taken.status = PlanStatus.NEGOTIATING
            taken.assigned_agent_id = agent_id
            await agent_repo.save(taken)
            await agent_session.commit()

        stale.request_quote(later)
        with pytest.raises(InvalidTransition):
            await first_repo.save(stale)

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert read.status is PlanStatus.NEGOTIATING
    assert read.assigned_agent_id == agent_id


async def test_list_queue_returns_requested_plans_oldest_first(engine, wish_id, offer_ids):
    hotel, _boat = offer_ids
    first = Plan.propose(wish_id, True, "First", [DraftItem(hotel, 1, 7, None)], 8, NOW)
    second = Plan.propose(
        wish_id,
        True,
        "Second",
        [DraftItem(hotel, 1, 7, None)],
        8,
        datetime(2026, 10, 19, 10, 0, tzinfo=UTC),
    )
    first.request_quote(NOW)
    second.request_quote(datetime(2026, 10, 19, 10, 0, tzinfo=UTC))
    await add_plan(engine, second)
    await add_plan(engine, first)

    async with new_session(engine) as session:
        listed = await SqlPlanRepository(session).list_queue([PlanStatus.REQUESTED], uuid4())

    assert [plan.id for plan in listed] == [first.id, second.id]
    assert all(plan.status is PlanStatus.REQUESTED for plan in listed)
    assert all(plan.items == () for plan in listed)


async def test_list_queue_pages(engine, wish_id, offer_ids):
    hotel, _boat = offer_ids
    plans = []
    for hour in (8, 9, 10):
        plan = Plan.propose(
            wish_id,
            True,
            f"Trip {hour}",
            [DraftItem(hotel, 1, 7, None)],
            8,
            datetime(2026, 10, 19, hour, 0, tzinfo=UTC),
        )
        plan.request_quote(plan.created_at)
        await add_plan(engine, plan)
        plans.append(plan)

    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        agent_id = uuid4()
        first_page = await repo.list_queue([PlanStatus.REQUESTED], agent_id, limit=2, offset=0)
        second_page = await repo.list_queue([PlanStatus.REQUESTED], agent_id, limit=2, offset=2)

    assert [plan.id for plan in first_page] == [plans[0].id, plans[1].id]
    assert [plan.id for plan in second_page] == [plans[2].id]


async def _queued_plan(
    engine, wish_id, hotel: UUID, hour: int, status: PlanStatus, agent_id: UUID | None = None
) -> Plan:
    at = datetime(2026, 10, 19, hour, 0, tzinfo=UTC)
    plan = Plan.propose(wish_id, True, f"Trip {hour}", [DraftItem(hotel, 1, 7, None)], 8, at)
    plan.request_quote(at)
    if agent_id is not None:
        plan.take(agent_id, at)
    plan.status = status
    await add_plan(engine, plan)
    return plan


async def test_list_queue_lists_only_my_plans_for_other_statuses(engine, wish_id, offer_ids):
    hotel, _boat = offer_ids
    me, other = uuid4(), uuid4()
    await _add_agent(engine, me)
    await _add_agent(engine, other)
    await _queued_plan(engine, wish_id, hotel, 8, PlanStatus.REQUESTED)
    mine = await _queued_plan(engine, wish_id, hotel, 9, PlanStatus.NEGOTIATING, me)
    await _queued_plan(engine, wish_id, hotel, 10, PlanStatus.NEGOTIATING, other)

    async with new_session(engine) as session:
        listed = await SqlPlanRepository(session).list_queue([PlanStatus.NEGOTIATING], me)

    assert [plan.id for plan in listed] == [mine.id]


async def test_list_queue_mixes_everyones_requested_with_my_other_statuses(
    engine, wish_id, offer_ids
):
    hotel, _boat = offer_ids
    me, other = uuid4(), uuid4()
    await _add_agent(engine, me)
    await _add_agent(engine, other)
    my_quoted = await _queued_plan(engine, wish_id, hotel, 8, PlanStatus.QUOTED, me)
    await _queued_plan(engine, wish_id, hotel, 9, PlanStatus.QUOTED, other)
    requested = await _queued_plan(engine, wish_id, hotel, 10, PlanStatus.REQUESTED)
    await _queued_plan(engine, wish_id, hotel, 11, PlanStatus.NEGOTIATING, me)
    my_accepted = await _queued_plan(engine, wish_id, hotel, 12, PlanStatus.ACCEPTED, me)

    async with new_session(engine) as session:
        listed = await SqlPlanRepository(session).list_queue(
            [PlanStatus.REQUESTED, PlanStatus.QUOTED, PlanStatus.ACCEPTED], me
        )

    assert [plan.id for plan in listed] == [my_quoted.id, requested.id, my_accepted.id]


async def test_list_queue_pages_across_mixed_statuses(engine, wish_id, offer_ids):
    hotel, _boat = offer_ids
    me = uuid4()
    await _add_agent(engine, me)
    await _queued_plan(engine, wish_id, hotel, 8, PlanStatus.REQUESTED)
    my_quoted = await _queued_plan(engine, wish_id, hotel, 9, PlanStatus.QUOTED, me)
    late = await _queued_plan(engine, wish_id, hotel, 10, PlanStatus.REQUESTED)

    async with new_session(engine) as session:
        page = await SqlPlanRepository(session).list_queue(
            [PlanStatus.REQUESTED, PlanStatus.QUOTED], me, limit=2, offset=1
        )

    assert [plan.id for plan in page] == [my_quoted.id, late.id]


async def test_a_second_take_does_not_steal_the_plan(engine, wish_id, offer_ids):
    hotel, _boat = offer_ids
    later = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    first_agent, second_agent = uuid4(), uuid4()
    plan = Plan.propose(wish_id, True, "Sun and sea", [DraftItem(hotel, 1, 7, None)], 8, NOW)
    plan.request_quote(NOW)
    await add_plan(engine, plan)
    async with new_session(engine) as session:
        session.add_all(
            [
                UserModel(id=first_agent, email=f"{first_agent}@example.com", created_at=NOW),
                UserModel(id=second_agent, email=f"{second_agent}@example.com", created_at=NOW),
            ]
        )
        await session.commit()

    async with new_session(engine) as first:
        first_repo = SqlPlanRepository(first)
        held = await first_repo.get(plan.id)
        async with new_session(engine) as second:
            second_repo = SqlPlanRepository(second)
            rival = await second_repo.get(plan.id)
            await second.commit()
            rival.take(second_agent, later)
            await second_repo.save(rival)
            await second.commit()
        held.take(first_agent, later)
        with pytest.raises(InvalidTransition):
            await first_repo.save(held)

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert read.status is PlanStatus.NEGOTIATING
    assert read.assigned_agent_id == second_agent


class _Contacts:
    async def contacts_for(self, offer_ids):
        return []


class _NoTrips:
    async def for_wish_ids(self, wish_ids):
        return {}


class _SessionUow:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 10, 19, 10, 0, tzinfo=UTC)


async def _add_agent(engine: AsyncEngine, agent_id: UUID) -> None:
    async with new_session(engine) as session:
        session.add(UserModel(id=agent_id, email=f"{agent_id}@example.com", created_at=NOW))
        await session.commit()


async def _requested_two_item_plan(engine, wish_id, offer_ids) -> Plan:
    hotel, boat = offer_ids
    plan = Plan.propose(
        wish_id,
        True,
        "Sun and sea",
        [DraftItem(hotel, 1, 7, None), DraftItem(boat, 3, 2, None)],
        8,
        NOW,
    )
    plan.request_quote(NOW)
    await add_plan(engine, plan)
    return plan


async def test_take_plan_in_one_session_returns_negotiating(engine, wish_id, offer_ids):
    agent_id = uuid4()
    plan = await _requested_two_item_plan(engine, wish_id, offer_ids)
    await _add_agent(engine, agent_id)

    async with new_session(engine) as session:
        view = await TakePlan(
            SqlPlanRepository(session), _Contacts(), _NoTrips(), _SessionUow(session), _Clock()
        )(plan.id, agent_id)

    assert view.status == "negotiating"
    assert view.assigned_agent_id == agent_id


async def test_set_item_price_in_one_session_returns_the_saved_price(engine, wish_id, offer_ids):
    agent_id = uuid4()
    later = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    plan = await _requested_two_item_plan(engine, wish_id, offer_ids)
    await _add_agent(engine, agent_id)
    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        loaded = await repo.get(plan.id)
        loaded.take(agent_id, later)
        await repo.save(loaded)
        await session.commit()

    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        loaded = await repo.get(plan.id)
        view = await SetItemPrice(repo, _Contacts(), _NoTrips(), _SessionUow(session), _Clock())(
            SetItemCommand(plan.id, loaded.items[0].id, agent_id, Decimal("120.00"), None)
        )

    assert view.items[0].negotiated_price == Decimal("120.00")
    assert view.total == Decimal("120.00")


async def test_a_stale_price_does_not_restore_a_removed_item(engine, wish_id, offer_ids):
    agent_id = uuid4()
    later = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    plan = await _requested_two_item_plan(engine, wish_id, offer_ids)
    await _add_agent(engine, agent_id)
    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        taken = await repo.get(plan.id)
        taken.take(agent_id, later)
        await repo.save(taken)
        await session.commit()

    async with new_session(engine) as first:
        first_repo = SqlPlanRepository(first)
        tab_one = await first_repo.get(plan.id)
        async with new_session(engine) as second:
            second_repo = SqlPlanRepository(second)
            tab_two = await second_repo.get(plan.id)
            await second.commit()
            tab_two.remove_item(tab_two.items[0].id, agent_id, later)
            await second_repo.save_item(tab_two, tab_two.items[0].id, ItemWrite.REMOVE)
            await second.commit()
        tab_one.set_item_price(tab_one.items[0].id, agent_id, Decimal("300.00"), later)
        with pytest.raises(InvalidTransition):
            await first_repo.save_item(tab_one, tab_one.items[0].id, ItemWrite.PRICE)

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert read.items[0].removed is True
    assert read.items[0].negotiated_price is None


async def test_a_stale_restore_does_not_roll_back_a_price(engine, wish_id, offer_ids):
    agent_id = uuid4()
    later = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    plan = await _requested_two_item_plan(engine, wish_id, offer_ids)
    await _add_agent(engine, agent_id)
    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        taken = await repo.get(plan.id)
        taken.take(agent_id, later)
        await repo.save(taken)
        await session.commit()

    async with new_session(engine) as first:
        first_repo = SqlPlanRepository(first)
        tab_one = await first_repo.get(plan.id)
        async with new_session(engine) as second:
            second_repo = SqlPlanRepository(second)
            tab_two = await second_repo.get(plan.id)
            await second.commit()
            tab_two.set_item_price(tab_two.items[0].id, agent_id, Decimal("150.00"), later)
            await second_repo.save_item(tab_two, tab_two.items[0].id, ItemWrite.PRICE)
            await second.commit()
        await first_repo.save_item(tab_one, tab_one.items[0].id, ItemWrite.RESTORE)

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert read.items[0].removed is False
    assert read.items[0].negotiated_price == Decimal("150.00")


async def _add_extras(engine: AsyncEngine) -> tuple[UUID, UUID]:
    bag = ExtraRow(
        id=uuid4(),
        category="transport",
        label="Extra bag",
        description="One more bag in the hold",
        pricing="supplement",
        supplement_eur=25,
        unit="per bag",
        constraints=[],
        active=True,
    )
    guide = ExtraRow(
        id=uuid4(),
        category="activity",
        label="Private guide",
        description="A guide for the group",
        pricing="on_quote",
        supplement_eur=None,
        unit="per activity",
        constraints=[],
        active=True,
    )
    async with new_session(engine) as session:
        session.add_all([bag, guide])
        await session.commit()
    return bag.id, guide.id


async def test_save_writes_the_chosen_extras_when_the_quote_is_requested(
    engine, wish_id, offer_ids
):
    hotel, _boat = offer_ids
    bag, guide = await _add_extras(engine)
    plan = Plan.propose(wish_id, True, "Sun and sea", [DraftItem(hotel, 1, 7, None)], 8, NOW)
    await add_plan(engine, plan)
    extras = [
        PlanExtra(extra_id=bag, pricing="supplement", price_eur=Decimal("25.00")),
        PlanExtra(extra_id=guide, pricing="on_quote", price_eur=None),
    ]

    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        loaded = await repo.get(plan.id)
        loaded.request_quote(NOW, extras)
        await repo.save(loaded)
        await session.commit()

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert {extra.extra_id: extra for extra in read.extras} == {
        extra.extra_id: extra for extra in extras
    }


async def test_save_extra_writes_the_price_the_agent_set(engine, wish_id, offer_ids):
    hotel, _boat = offer_ids
    _bag, guide = await _add_extras(engine)
    agent_id = uuid4()
    await _add_agent(engine, agent_id)
    plan = Plan.propose(wish_id, True, "Sun and sea", [DraftItem(hotel, 1, 7, None)], 8, NOW)
    await add_plan(engine, plan)
    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        loaded = await repo.get(plan.id)
        loaded.request_quote(NOW, [PlanExtra(extra_id=guide, pricing="on_quote", price_eur=None)])
        await repo.save(loaded)
        loaded.take(agent_id, NOW)
        await repo.save(loaded)
        await session.commit()

    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        loaded = await repo.get(plan.id)
        loaded.set_extra_price(guide, agent_id, Decimal("45.00"), NOW)
        await repo.save_extra(loaded, guide)
        await session.commit()

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert read.extras == (
        PlanExtra(extra_id=guide, pricing="on_quote", price_eur=Decimal("45.00")),
    )
    assert read.extras[0].confirmed is True


async def test_a_chosen_extra_is_not_confirmed_until_the_agent_prices_it(
    engine, wish_id, offer_ids
):
    hotel, _boat = offer_ids
    bag, _guide = await _add_extras(engine)
    plan = Plan.propose(wish_id, True, "Sun and sea", [DraftItem(hotel, 1, 7, None)], 8, NOW)
    await add_plan(engine, plan)
    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        loaded = await repo.get(plan.id)
        loaded.request_quote(
            NOW, [PlanExtra(extra_id=bag, pricing="supplement", price_eur=Decimal("25.00"))]
        )
        await repo.save(loaded)
        await session.commit()

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert read.extras[0].confirmed is False


async def test_the_extra_label_and_unit_are_stored_with_the_plan(engine, wish_id, offer_ids):
    hotel, _boat = offer_ids
    bag, _guide = await _add_extras(engine)
    plan = Plan.propose(wish_id, True, "Sun and sea", [DraftItem(hotel, 1, 7, None)], 8, NOW)
    await add_plan(engine, plan)
    chosen = PlanExtra(
        extra_id=bag,
        pricing="supplement",
        price_eur=Decimal("25.00"),
        label="Extra bag",
        unit="per bag",
    )

    async with new_session(engine) as session:
        repo = SqlPlanRepository(session)
        loaded = await repo.get(plan.id)
        loaded.request_quote(NOW, [chosen])
        await repo.save(loaded)
        await session.commit()

    read = await read_plan(engine, plan.id)
    assert read is not None
    assert [(extra.label, extra.unit) for extra in read.extras] == [("Extra bag", "per bag")]
