"""The Quote entity: number, currency, validity and the rule on its total."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from novoya_api.quoting.domain.errors import InvalidQuote, QuoteNotFound
from novoya_api.quoting.domain.quote import AGENCY_TIMEZONE, VALIDITY, Quote, QuoteStatus
from novoya_api.shared.domain.errors import InvalidInput, NotFound
from novoya_api.shared.domain.value_objects import Locale

PLAN_ID = UUID("00000000-0000-0000-0000-0000000000d1")
CLIENT_ID = UUID("00000000-0000-0000-0000-000000000001")
AGENT_ID = UUID("00000000-0000-0000-0000-0000000000aa")
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)


def issue(total: Decimal = Decimal("1234.50"), locale: Locale = Locale.FR) -> Quote:
    return Quote.issue(PLAN_ID, CLIENT_ID, AGENT_ID, total, locale, NOW)


def test_a_quote_keeps_the_plan_the_people_and_the_total():
    quote = issue()

    assert (quote.plan_id, quote.client_id, quote.agent_id) == (PLAN_ID, CLIENT_ID, AGENT_ID)
    assert quote.total == Decimal("1234.50")
    assert quote.locale is Locale.FR
    assert quote.sent_at == NOW


def test_a_quote_is_in_euros():
    assert issue().currency == "EUR"


def test_a_quote_is_valid_for_seven_days_after_sending():
    assert VALIDITY == timedelta(days=7)
    assert issue().valid_until == datetime(2026, 10, 26, 9, 0, tzinfo=UTC)


# valid_until is 26 October 09:00 UTC, 10:00 in Paris (winter time from 25 October).
LAST_MINUTE_IN_PARIS = datetime(2026, 10, 26, 23, 59, tzinfo=AGENCY_TIMEZONE)
NEXT_DAY_IN_PARIS = datetime(2026, 10, 27, 0, 0, tzinfo=AGENCY_TIMEZONE)


def test_a_quote_is_open_until_the_end_of_its_last_day_in_paris():
    quote = issue()

    assert quote.status(LAST_MINUTE_IN_PARIS) is QuoteStatus.OPEN
    assert not quote.has_expired(LAST_MINUTE_IN_PARIS)


def test_a_quote_expires_when_the_next_day_starts_in_paris():
    quote = issue()

    assert quote.status(NEXT_DAY_IN_PARIS) is QuoteStatus.EXPIRED


def test_the_answer_is_the_status_even_after_the_validity():
    quote = issue()
    quote.answer = QuoteStatus.REJECTED

    assert quote.status(NOW) is QuoteStatus.REJECTED
    assert quote.status(NEXT_DAY_IN_PARIS) is QuoteStatus.REJECTED


def test_the_number_has_the_date_and_the_start_of_the_id():
    quote = issue()

    assert quote.number == f"NV-20261019-{quote.id.hex[:6].upper()}"


def test_each_quote_gets_its_own_id():
    assert issue().id != issue().id


def test_a_new_quote_has_no_pdf_yet():
    assert issue().pdf is None


@pytest.mark.parametrize("total", [Decimal("0"), Decimal("-1")], ids=["zero", "negative"])
def test_a_quote_needs_a_total_above_zero(total):
    with pytest.raises(InvalidQuote):
        issue(total)


def test_quote_errors_map_to_the_shared_errors():
    assert issubclass(InvalidQuote, InvalidInput)
    assert issubclass(QuoteNotFound, NotFound)


def test_the_number_has_the_paris_date():
    late_evening_utc = datetime(2026, 10, 22, 22, 30, tzinfo=UTC)  # 00:30 on the 23rd in Paris

    quote = Quote.issue(PLAN_ID, CLIENT_ID, AGENT_ID, Decimal("10"), Locale.FR, late_evening_utc)

    assert quote.number.startswith("NV-20261023-")
