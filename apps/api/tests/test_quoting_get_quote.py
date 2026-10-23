"""GetQuote: a quote and where it stands, on fakes."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from novoya_api.quoting.application.use_cases.get_quote import GetQuote
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.quoting.domain.quote import Quote, QuoteStatus
from tests.quoting_fakes import (
    AGENT,
    AGENT_ID,
    CLIENT_FR,
    CLIENT_ID,
    NOW,
    OTHER_AGENT,
    OTHER_CLIENT,
    QUOTED,
    FakePeople,
    FakePlanQuoting,
    FakeQuotes,
    FixedClock,
    stored_quote,
)

QUOTE = stored_quote()
# Two days after the validity date: whatever the time of day, the last day is over.
AFTER = QUOTE.valid_until + timedelta(days=2)


def use_case(
    now: datetime = NOW, quote: Quote = QUOTE, plans: FakePlanQuoting | None = None
) -> GetQuote:
    people = FakePeople(CLIENT_FR, AGENT)
    return GetQuote(FakeQuotes(quote), plans or FakePlanQuoting(), people, FixedClock(now))


async def test_the_client_reads_their_open_quote():
    detail = await use_case()(QUOTE.id, CLIENT_ID, admin=False)

    assert detail.status == QuoteStatus.OPEN
    assert detail.id == QUOTE.id
    assert detail.number == QUOTE.number
    assert detail.total == QUOTE.total


async def test_the_quote_shows_the_trip_its_lines_and_who_prepared_it():
    detail = await use_case()(QUOTE.id, CLIENT_ID, admin=False)

    assert detail.agent_name == AGENT.name
    assert (detail.country, detail.city, detail.persons) == ("Greece", "Chania", 2)
    assert (detail.start_date, detail.end_date) == (QUOTED.start_date, QUOTED.end_date)
    assert detail.budget_max == QUOTED.budget_max
    assert detail.items == QUOTED.items
    assert detail.extras == QUOTED.extras
    assert (detail.decided_at, detail.client_comment) == (None, None)


async def test_a_quote_whose_plan_is_gone_still_reads():
    plans = FakePlanQuoting(priced_plan=None)

    detail = await use_case(plans=plans)(QUOTE.id, CLIENT_ID, admin=False)

    assert detail.id == QUOTE.id
    assert (detail.city, detail.items, detail.extras) == (None, (), ())


async def test_the_quote_is_still_open_on_its_last_instant():
    detail = await use_case(QUOTE.valid_until)(QUOTE.id, CLIENT_ID, admin=False)

    assert detail.status == QuoteStatus.OPEN


async def test_the_quote_is_expired_after_its_validity_date():
    detail = await use_case(AFTER)(QUOTE.id, CLIENT_ID, admin=False)

    assert detail.status == QuoteStatus.EXPIRED


@pytest.mark.parametrize("answer", [QuoteStatus.ACCEPTED, QuoteStatus.REJECTED])
async def test_the_clients_answer_is_the_status(answer):
    quote = stored_quote(answer)

    detail = await use_case(quote=quote)(quote.id, CLIENT_ID, admin=False)

    assert detail.status == answer
    assert detail.decided_at == quote.decided_at


async def test_an_answer_stays_after_the_validity_date():
    quote = stored_quote(QuoteStatus.ACCEPTED)

    detail = await use_case(AFTER, quote)(quote.id, CLIENT_ID, admin=False)

    assert detail.status == QuoteStatus.ACCEPTED


async def test_the_agent_who_sent_it_reads_the_quote():
    detail = await use_case()(QUOTE.id, AGENT_ID, admin=False)

    assert detail.id == QUOTE.id


async def test_an_admin_reads_any_quote():
    detail = await use_case()(QUOTE.id, uuid4(), admin=True)

    assert detail.id == QUOTE.id


async def test_another_agent_cannot_read_the_quote():
    with pytest.raises(QuoteNotFound):
        await use_case()(QUOTE.id, OTHER_AGENT, admin=False)


async def test_another_client_cannot_read_the_quote():
    with pytest.raises(QuoteNotFound):
        await use_case()(QUOTE.id, OTHER_CLIENT, admin=False)


async def test_a_missing_quote_is_not_found():
    with pytest.raises(QuoteNotFound):
        await use_case()(uuid4(), CLIENT_ID, admin=False)
