"""Finding the plan and the quote of a client's wishes, for the list of trips (#98).

Against PostgreSQL, with the fixtures of test_quoting_repository_sql.py: skipped when Postgres
does not answer.
"""

from uuid import uuid4

from sqlalchemy import select

from novoya_api.planning import public as planning_public
from novoya_api.quoting import public as quoting_public
from novoya_api.quoting.infrastructure.db.models import QuoteModel
from novoya_api.wishes import public as wishes_public
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_delete_user_data_sql import send_quote
from tests.test_quoting_repository_sql import (  # noqa: F401  (fixtures)
    engine,
    new_session,
    stored,
)


async def wish_ids_of(session, user_id):
    wishes = await wishes_public.wishes_for_user(user_id, session=session)
    return [wish.wish_id for wish in wishes]


async def test_plans_for_wishes_gives_the_plan_of_the_wish(engine, stored):  # noqa: F811
    async with new_session(engine) as session:
        wish_ids = await wish_ids_of(session, stored.client_id)
        plans = await planning_public.plans_for_wishes(wish_ids, session=session)

    assert list(plans) == wish_ids
    assert [plan.plan_id for plan in plans.values()] == [stored.plan_id]


async def test_plans_for_wishes_follows_the_status_of_the_plan(engine, stored):  # noqa: F811
    await send_quote(engine, stored)

    async with new_session(engine) as session:
        wish_ids = await wish_ids_of(session, stored.client_id)
        plans = await planning_public.plans_for_wishes(wish_ids, session=session)

    assert plans[wish_ids[0]].status == "quoted"


async def test_plans_for_wishes_leaves_out_a_wish_without_plan(engine, stored):  # noqa: F811
    async with new_session(engine) as session:
        assert await planning_public.plans_for_wishes([uuid4()], session=session) == {}
        assert await planning_public.plans_for_wishes([], session=session) == {}


async def test_quotes_for_plans_gives_the_quote_of_a_quoted_plan(engine, stored):  # noqa: F811
    await send_quote(engine, stored)

    async with new_session(engine) as session:
        quotes = await quoting_public.quotes_for_plans([stored.plan_id], session=session)
        quote_id = await session.scalar(select(QuoteModel.id))

    assert quotes == {stored.plan_id: quote_id}


async def test_quotes_for_plans_leaves_out_a_plan_not_quoted(engine, stored):  # noqa: F811
    async with new_session(engine) as session:
        assert await quoting_public.quotes_for_plans([stored.plan_id], session=session) == {}
        assert await quoting_public.quotes_for_plans([], session=session) == {}
