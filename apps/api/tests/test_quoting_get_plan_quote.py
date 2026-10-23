"""GetPlanQuote, tested with fake ports: the quote of a plan, for the agent who sent it or
an admin."""

from datetime import timedelta
from uuid import uuid4

import pytest

from novoya_api.quoting.application.dto import QuoteView
from novoya_api.quoting.application.use_cases.get_plan_quote import GetPlanQuote
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.quoting.domain.quote import QuoteStatus
from novoya_api.shared.domain.errors import PermissionDenied
from tests.quoting_fakes import (
    AGENT_ID,
    OTHER_AGENT,
    PLAN_ID,
    FakeQuotes,
    FixedClock,
    stored_quote,
)


async def test_the_assigned_agent_reads_the_quote_of_the_plan():
    quote = stored_quote()

    view = await GetPlanQuote(FakeQuotes(quote), FixedClock())(PLAN_ID, AGENT_ID, admin=False)

    assert view.quote == QuoteView.of(quote)
    assert view.status is QuoteStatus.OPEN
    assert (view.decided_at, view.client_comment) == (None, None)


async def test_the_agent_sees_the_clients_answer_and_comment():
    quote = stored_quote(QuoteStatus.REJECTED)
    quote.client_comment = "Too expensive for us"

    view = await GetPlanQuote(FakeQuotes(quote), FixedClock())(PLAN_ID, AGENT_ID, admin=False)

    assert view.status is QuoteStatus.REJECTED
    assert view.decided_at == quote.decided_at
    assert view.client_comment == "Too expensive for us"


async def test_an_answer_stays_after_the_validity_ends():
    quote = stored_quote(QuoteStatus.ACCEPTED)
    later = FixedClock(quote.valid_until + timedelta(days=2))

    view = await GetPlanQuote(FakeQuotes(quote), later)(PLAN_ID, AGENT_ID, admin=False)

    assert view.status is QuoteStatus.ACCEPTED


async def test_the_agent_sees_when_the_quote_expired_unanswered():
    quote = stored_quote()
    later = FixedClock(quote.valid_until + timedelta(days=2))

    view = await GetPlanQuote(FakeQuotes(quote), later)(PLAN_ID, AGENT_ID, admin=False)

    assert view.status is QuoteStatus.EXPIRED


async def test_a_plan_without_a_quote_is_not_found():
    with pytest.raises(QuoteNotFound):
        await GetPlanQuote(FakeQuotes(), FixedClock())(PLAN_ID, AGENT_ID, admin=False)


async def test_an_unknown_plan_is_not_found():
    with pytest.raises(QuoteNotFound):
        await GetPlanQuote(FakeQuotes(stored_quote()), FixedClock())(uuid4(), AGENT_ID, admin=False)


async def test_another_agent_cannot_read_the_quote_of_the_plan():
    with pytest.raises(PermissionDenied):
        await GetPlanQuote(FakeQuotes(stored_quote()), FixedClock())(
            PLAN_ID, OTHER_AGENT, admin=False
        )


async def test_an_admin_reads_the_quote_another_agent_sent():
    quote = stored_quote(QuoteStatus.ACCEPTED)

    view = await GetPlanQuote(FakeQuotes(quote), FixedClock())(PLAN_ID, uuid4(), admin=True)

    assert view.quote == QuoteView.of(quote)
    assert view.status is QuoteStatus.ACCEPTED
