"""AnswerQuote and GetQuote with their real adapters against PostgreSQL: the answer on the
quote and the plan's new status are committed together, and the quote page reads the trip
back from planning.

Uses the fixtures of test_quoting_repository_sql.py: skipped when Postgres does not answer.
"""

from decimal import Decimal

import pytest

from novoya_api.planning.domain.plan import PlanStatus
from novoya_api.planning.infrastructure.db.models import PlanModel
from novoya_api.quoting.domain.errors import QuoteAlreadyAnswered
from novoya_api.quoting.domain.quote import QuoteStatus
from novoya_api.quoting.infrastructure.db.models import QuoteModel
from novoya_api.quoting.presentation.http.dependencies import (
    get_answer_quote,
    get_get_quote,
    get_send_quote,
)
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_quoting_repository_sql import (  # noqa: F401  (fixtures)
    Stored,
    engine,
    new_session,
    stored,
)
from tests.test_quoting_send_quote_sql import negotiate


async def send(db, data: Stored):
    await negotiate(db, data, Decimal("640.00"))
    async with new_session(db) as session:
        return await get_send_quote(session)(data.plan_id, data.agent_id)


async def test_accepting_saves_the_answer_and_marks_the_plan_accepted(engine, stored):  # noqa: F811
    sent = await send(engine, stored)

    async with new_session(engine) as session:
        await get_answer_quote(session)(
            sent.id, stored.client_id, False, QuoteStatus.ACCEPTED, "Perfect"
        )

    async with new_session(engine) as session:
        plan = await session.get(PlanModel, stored.plan_id)
        quote = await session.get(QuoteModel, sent.id)
    assert plan.status == PlanStatus.ACCEPTED.value
    assert (quote.answer, quote.client_comment) == ("accepted", "Perfect")
    assert quote.decided_at is not None


async def test_a_second_answer_changes_nothing(engine, stored):  # noqa: F811
    sent = await send(engine, stored)
    async with new_session(engine) as session:
        await get_answer_quote(session)(
            sent.id, stored.client_id, False, QuoteStatus.REJECTED, None
        )

    async with new_session(engine) as session:
        with pytest.raises(QuoteAlreadyAnswered):
            await get_answer_quote(session)(
                sent.id, stored.client_id, False, QuoteStatus.ACCEPTED, None
            )

    async with new_session(engine) as session:
        plan = await session.get(PlanModel, stored.plan_id)
        quote = await session.get(QuoteModel, sent.id)
    assert plan.status == PlanStatus.REJECTED.value
    assert quote.answer == "rejected"


async def test_the_quote_page_reads_the_trip_and_the_lines(engine, stored):  # noqa: F811
    sent = await send(engine, stored)

    async with new_session(engine) as session:
        detail = await get_get_quote(session)(sent.id, stored.client_id, False)

    assert detail.status is QuoteStatus.OPEN
    assert [item.price for item in detail.items] == [Decimal("640.00")]
    assert detail.total == Decimal("640.00")
