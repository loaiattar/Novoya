"""GetPlanQuote, tested with fake ports: the quote of a plan, for the agent who sent it."""

from uuid import uuid4

import pytest

from novoya_api.quoting.application.dto import QuoteView
from novoya_api.quoting.application.use_cases.get_plan_quote import GetPlanQuote
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.shared.domain.errors import PermissionDenied
from tests.quoting_fakes import AGENT_ID, OTHER_AGENT, PLAN_ID, FakeQuotes, stored_quote


async def test_the_assigned_agent_reads_the_quote_of_the_plan():
    quote = stored_quote()

    view = await GetPlanQuote(FakeQuotes(quote))(PLAN_ID, AGENT_ID)

    assert view == QuoteView.of(quote)


async def test_a_plan_without_a_quote_is_not_found():
    with pytest.raises(QuoteNotFound):
        await GetPlanQuote(FakeQuotes())(PLAN_ID, AGENT_ID)


async def test_an_unknown_plan_is_not_found():
    with pytest.raises(QuoteNotFound):
        await GetPlanQuote(FakeQuotes(stored_quote()))(uuid4(), AGENT_ID)


async def test_another_agent_cannot_read_the_quote_of_the_plan():
    with pytest.raises(PermissionDenied):
        await GetPlanQuote(FakeQuotes(stored_quote()))(PLAN_ID, OTHER_AGENT)
