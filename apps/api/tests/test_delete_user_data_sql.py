"""Erasing a client's data in the order DELETE /me will use (#46): quotes, then plans, then
wishes. Against PostgreSQL, with a quoted plan: the case a missing step breaks.

Uses the fixtures of test_quoting_repository_sql.py: skipped when Postgres does not answer.
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from novoya_api.planning import public as planning_public
from novoya_api.planning.infrastructure.db.models import PlanModel
from novoya_api.quoting import public as quoting_public
from novoya_api.quoting.infrastructure.db.models import QuoteModel
from novoya_api.quoting.presentation.http.dependencies import get_send_quote
from novoya_api.wishes import public as wishes_public
from novoya_api.wishes.infrastructure.db.models import WishModel
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_quoting_repository_sql import (  # noqa: F401  (fixtures)
    Stored,
    engine,
    new_session,
    stored,
)
from tests.test_quoting_send_quote_sql import negotiate


async def send_quote(db, data: Stored) -> None:
    await negotiate(db, data, Decimal("640.00"))
    async with new_session(db) as session:
        await get_send_quote(session)(data.plan_id, data.agent_id)


async def count(db, model, *where) -> int:
    async with new_session(db) as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


async def test_a_quoted_clients_data_is_erased_in_order(engine, stored):  # noqa: F811
    await send_quote(engine, stored)

    async with new_session(engine) as session:
        await quoting_public.delete_for_user(stored.client_id, session=session)
        await planning_public.delete_for_user(stored.client_id, session=session)
        await wishes_public.delete_for_user(stored.client_id, session=session)
        await session.commit()

    assert await count(engine, QuoteModel) == 0
    assert await count(engine, PlanModel) == 0
    assert await count(engine, WishModel, WishModel.user_id == stored.client_id) == 0


async def test_plans_with_a_quote_cannot_go_before_the_quote(engine, stored):  # noqa: F811
    await send_quote(engine, stored)

    async with new_session(engine) as session:
        with pytest.raises(IntegrityError):
            await planning_public.delete_for_user(stored.client_id, session=session)
            await session.commit()


async def test_quoting_delete_for_user_leaves_other_clients_quotes(engine, stored):  # noqa: F811
    await send_quote(engine, stored)

    async with new_session(engine) as session:
        await quoting_public.delete_for_user(stored.agent_id, session=session)
        await session.commit()

    assert await count(engine, QuoteModel) == 1
