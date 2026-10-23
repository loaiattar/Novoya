"""Custom plans (#184) against a real PostgreSQL: the flag and the agent's outline read back,
and an item the agent adds is written with no price, only while the status is unchanged.

Uses the database fixtures of test_planning_repository_sql.py: skipped without Postgres.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from novoya_api.accounts.infrastructure.db.models import UserModel
from novoya_api.planning.domain.plan import DraftItem, Plan, PlanStatus
from novoya_api.planning.infrastructure.db.repository import SqlPlanRepository
from novoya_api.planning.public import TripDates, closest_trip_dates
from novoya_api.shared.domain.errors import InvalidTransition
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_planning_repository_sql import (  # noqa: F401  (fixtures)
    add_plan,
    engine,
    new_session,
    offer_ids,
    read_plan,
    wish_id,
)

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)


async def test_a_custom_plan_reads_back_requested_with_its_outline_and_no_item(
    engine,  # noqa: F811
    wish_id,  # noqa: F811
):
    plan = Plan.custom_request(wish_id, False, "A custom request", "Day 1: arrive", NOW)

    await add_plan(engine, plan)
    stored = await read_plan(engine, plan.id)

    assert stored is not None
    assert stored.status is PlanStatus.REQUESTED
    assert stored.custom is True
    assert stored.outline == "Day 1: arrive"
    assert stored.items == ()


async def test_a_plan_the_app_builds_is_not_custom(engine, wish_id, offer_ids):  # noqa: F811
    hotel, _boat = offer_ids
    plan = Plan.propose(wish_id, False, "A week by the sea", [DraftItem(hotel, 1, 1, None)], 2, NOW)

    await add_plan(engine, plan)

    stored = await read_plan(engine, plan.id)
    assert stored is not None and stored.custom is False and stored.outline is None


async def take(engine, plan: Plan):  # noqa: F811
    agent_id = uuid4()
    async with new_session(engine) as session:
        session.add(UserModel(id=agent_id, email=f"{agent_id}@example.com", created_at=NOW))
        await session.commit()
    async with new_session(engine) as session:
        plans = SqlPlanRepository(session)
        taken = await plans.get(plan.id)
        assert taken is not None
        taken.take(agent_id, NOW)
        await plans.save(taken)
        await session.commit()
    return agent_id


async def test_an_added_item_is_written_with_no_price(engine, wish_id, offer_ids):  # noqa: F811
    hotel, boat = offer_ids
    plan = Plan.custom_request(wish_id, True, "A custom request", None, NOW)
    await add_plan(engine, plan)
    agent_id = await take(engine, plan)

    async with new_session(engine) as session:
        plans = SqlPlanRepository(session)
        working = await plans.get(plan.id)
        assert working is not None
        item = working.add_item(boat, 2, 1, "Morning", agent_id, LATER)
        await plans.add_item(working, item.id)
        await session.commit()

    stored = await read_plan(engine, plan.id)
    assert stored is not None
    [added] = stored.items
    assert (added.id, added.offer_id, added.day, added.quantity, added.note) == (
        item.id,
        boat,
        2,
        1,
        "Morning",
    )
    assert added.negotiated_price is None and added.removed is False
    assert stored.updated_at == LATER


async def test_an_item_is_not_added_once_another_tab_changed_the_status(
    engine,  # noqa: F811
    wish_id,  # noqa: F811
    offer_ids,  # noqa: F811
):
    hotel, boat = offer_ids
    plan = Plan.custom_request(wish_id, True, "A custom request", None, NOW)
    await add_plan(engine, plan)
    agent_id = await take(engine, plan)

    async with new_session(engine) as stale_session:
        stale = SqlPlanRepository(stale_session)
        working = await stale.get(plan.id)
        assert working is not None
        # Meanwhile another request moves the plan on (written directly, as a quote would).
        async with new_session(engine) as other:
            plans = SqlPlanRepository(other)
            moved = await plans.get(plan.id)
            assert moved is not None
            moved.status = PlanStatus.QUOTED
            await plans.save(moved)
            await other.commit()
        item = working.add_item(boat, 2, 1, None, agent_id, LATER)
        with pytest.raises(InvalidTransition):
            await stale.add_item(working, item.id)
        await stale_session.rollback()

    stored = await read_plan(engine, plan.id)
    assert stored is not None and stored.items == ()


async def test_the_closest_dates_are_read_from_the_real_catalog(engine, offer_ids):  # noqa: F811
    # The offers are open from 1 April to 31 October 2026, for up to 4 travellers.
    async with new_session(engine) as session:
        found = await closest_trip_dates(
            "Greece",
            "Chania",
            2,
            date(2026, 11, 5),
            date(2026, 11, 7),
            date(2026, 10, 23),
            session=session,
        )
        too_many = await closest_trip_dates(
            "Greece",
            "Chania",
            5,
            date(2026, 11, 5),
            date(2026, 11, 7),
            date(2026, 10, 23),
            session=session,
        )

    # The last 3-day trip with an open day starts on 31 October; nothing after.
    assert found == [TripDates(date(2026, 10, 31), date(2026, 11, 2), 2)]
    assert too_many == []
