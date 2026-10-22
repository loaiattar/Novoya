"""GetQuote: a quote and where it stands, on fakes."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from novoya_api.quoting.application.use_cases.get_quote import GetQuote
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.quoting.domain.quote import QuoteStatus
from tests.quoting_fakes import (
    AGENT_ID,
    CLIENT_ID,
    NOW,
    OTHER_CLIENT,
    FakePlanQuoting,
    FakeQuotes,
    FixedClock,
    stored_quote,
)

QUOTE = stored_quote()


def use_case(now: datetime = NOW, answer: QuoteStatus | None = None) -> GetQuote:
    return GetQuote(FakeQuotes(QUOTE), FakePlanQuoting(answer=answer), FixedClock(now))


async def test_the_client_reads_their_open_quote():
    detail = await use_case()(QUOTE.id, CLIENT_ID, staff=False)

    assert detail.status == QuoteStatus.OPEN
    assert detail.id == QUOTE.id
    assert detail.number == QUOTE.number
    assert detail.total == QUOTE.total


async def test_the_quote_is_still_open_on_its_last_instant():
    detail = await use_case(QUOTE.valid_until)(QUOTE.id, CLIENT_ID, staff=False)

    assert detail.status == QuoteStatus.OPEN


async def test_the_quote_is_expired_after_its_validity_date():
    later = QUOTE.valid_until + timedelta(seconds=1)

    detail = await use_case(later)(QUOTE.id, CLIENT_ID, staff=False)

    assert detail.status == QuoteStatus.EXPIRED


@pytest.mark.parametrize("answer", [QuoteStatus.ACCEPTED, QuoteStatus.REJECTED])
async def test_the_clients_answer_is_the_status(answer):
    detail = await use_case(answer=answer)(QUOTE.id, CLIENT_ID, staff=False)

    assert detail.status == answer


async def test_an_answer_stays_after_the_validity_date():
    later = QUOTE.valid_until + timedelta(days=1)

    detail = await use_case(later, QuoteStatus.ACCEPTED)(QUOTE.id, CLIENT_ID, staff=False)

    assert detail.status == QuoteStatus.ACCEPTED


async def test_staff_read_any_quote():
    detail = await use_case()(QUOTE.id, AGENT_ID, staff=True)

    assert detail.id == QUOTE.id


async def test_another_client_cannot_read_the_quote():
    with pytest.raises(QuoteNotFound):
        await use_case()(QUOTE.id, OTHER_CLIENT, staff=False)


async def test_a_missing_quote_is_not_found():
    with pytest.raises(QuoteNotFound):
        await use_case()(uuid4(), CLIENT_ID, staff=False)
