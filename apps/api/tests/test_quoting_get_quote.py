"""GetQuote: a quote and where it stands, on fakes."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from novoya_api.quoting.application.use_cases.get_quote import GetQuote
from novoya_api.quoting.domain.errors import QuoteNotFound
from tests.quoting_fakes import AGENT_ID, CLIENT_ID, NOW, OTHER_CLIENT, FakeQuotes, stored_quote

QUOTE = stored_quote()


class ClockAt:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


def use_case(now: datetime = NOW) -> GetQuote:
    return GetQuote(FakeQuotes(QUOTE), ClockAt(now))


async def test_the_client_reads_their_open_quote():
    detail = await use_case()(QUOTE.id, CLIENT_ID, staff=False)

    assert detail.status == "open"
    assert detail.quote.id == QUOTE.id
    assert detail.quote.number == QUOTE.number
    assert detail.quote.total == QUOTE.total


async def test_the_quote_is_still_open_on_its_last_instant():
    detail = await use_case(QUOTE.valid_until)(QUOTE.id, CLIENT_ID, staff=False)

    assert detail.status == "open"


async def test_the_quote_is_expired_after_its_validity_date():
    later = QUOTE.valid_until + timedelta(seconds=1)

    detail = await use_case(later)(QUOTE.id, CLIENT_ID, staff=False)

    assert detail.status == "expired"


async def test_staff_read_any_quote():
    detail = await use_case()(QUOTE.id, AGENT_ID, staff=True)

    assert detail.quote.id == QUOTE.id


async def test_another_client_cannot_read_the_quote():
    with pytest.raises(QuoteNotFound):
        await use_case()(QUOTE.id, OTHER_CLIENT, staff=False)


async def test_a_missing_quote_is_not_found():
    with pytest.raises(QuoteNotFound):
        await use_case()(uuid4(), CLIENT_ID, staff=False)
