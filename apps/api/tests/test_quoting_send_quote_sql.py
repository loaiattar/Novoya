"""SendQuote with its real adapters against PostgreSQL: the plan's new status and the quote
are committed together, or neither is.

Uses the fixtures of test_quoting_repository_sql.py: skipped when Postgres does not answer.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select

from novoya_api.planning.application.ports.plan_repository import ItemWrite
from novoya_api.planning.domain.errors import PlanNotReady
from novoya_api.planning.domain.plan import PlanStatus
from novoya_api.planning.infrastructure.db.models import PlanModel
from novoya_api.planning.infrastructure.db.repository import SqlPlanRepository
from novoya_api.quoting.infrastructure.db.models import QuoteModel
from novoya_api.quoting.presentation.http.dependencies import get_send_quote
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_quoting_repository_sql import (  # noqa: F401  (fixtures)
    NOW,
    Stored,
    engine,
    new_session,
    stored,
)


async def negotiate(db, data: Stored, price: Decimal | None) -> None:
    """The client asks for a quote, the agent takes the plan and prices its item (or not)."""
    async with new_session(db) as session:
        plans = SqlPlanRepository(session)
        plan = await plans.get(data.plan_id)
        plan.request_quote(NOW)
        await plans.save(plan)
        plan.take(data.agent_id, NOW)
        await plans.save(plan)
        if price is not None:
            item_id = plan.items[0].id
            plan.set_item_price(item_id, data.agent_id, price, NOW)
            await plans.save_item(plan, item_id, ItemWrite.PRICE)
        await session.commit()


async def test_sending_saves_the_quote_and_marks_the_plan_quoted(engine, stored):  # noqa: F811
    await negotiate(engine, stored, Decimal("640.00"))

    async with new_session(engine) as session:
        view = await get_send_quote(session)(stored.plan_id, stored.agent_id)

    async with new_session(engine) as session:
        plan = await session.get(PlanModel, stored.plan_id)
        quote = await session.get(QuoteModel, view.id)
    assert plan.status == PlanStatus.QUOTED.value
    assert quote.total_price == Decimal("640.00")
    assert quote.client_id == stored.client_id
    assert quote.pdf.startswith(b"%PDF")


async def test_a_plan_not_ready_leaves_no_quote_and_stays_negotiating(engine, stored):  # noqa: F811
    await negotiate(engine, stored, price=None)

    async with new_session(engine) as session:
        with pytest.raises(PlanNotReady):
            await get_send_quote(session)(stored.plan_id, stored.agent_id)

    async with new_session(engine) as session:
        plan = await session.get(PlanModel, stored.plan_id)
        quotes = (await session.scalars(select(QuoteModel))).all()
    assert plan.status == PlanStatus.NEGOTIATING.value
    assert quotes == []


class BrokenRenderer:
    def render(self, document) -> bytes:
        raise RuntimeError("WeasyPrint failed")


async def test_a_failure_after_the_plan_is_saved_leaves_it_negotiating(engine, stored):  # noqa: F811
    await negotiate(engine, stored, Decimal("640.00"))

    async with new_session(engine) as session:
        use_case = get_send_quote(session)
        use_case._renderer = BrokenRenderer()
        with pytest.raises(RuntimeError):
            await use_case(stored.plan_id, stored.agent_id)

    async with new_session(engine) as session:
        plan = await session.get(PlanModel, stored.plan_id)
        quotes = (await session.scalars(select(QuoteModel))).all()
    assert plan.status == PlanStatus.NEGOTIATING.value
    assert quotes == []
