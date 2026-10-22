"""ResendQuoteEmail, tested with fake ports."""

from uuid import uuid4

import pytest

from novoya_api.quoting.application.dto import QuoteTrip
from novoya_api.quoting.application.use_cases.resend_quote_email import ResendQuoteEmail
from novoya_api.quoting.domain.errors import QuoteEmailNotSent, QuoteNotFound
from novoya_api.shared.domain.errors import PermissionDenied, TooManyRequests
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from tests.quoting_fakes import (
    AGENT,
    AGENT_ID,
    CLIENT_FR,
    FRONTEND,
    TRIP,
    FakeNotifier,
    FakePeople,
    FakePlanQuoting,
    FakeQuotes,
    FixedClock,
    stored_quote,
)

QUOTE = stored_quote()  # in French, sent by AGENT_ID


def resend(notifier: FakeNotifier, plans: FakePlanQuoting | None = None, people=None, limiter=None):
    return ResendQuoteEmail(
        FakeQuotes(QUOTE),
        plans or FakePlanQuoting(),
        people or FakePeople(CLIENT_FR, AGENT),
        notifier,
        limiter or InMemoryRateLimiter(FixedClock()),
        FRONTEND,
    )


async def test_the_agent_who_sent_the_quote_resends_the_email():
    notifier = FakeNotifier()

    await resend(notifier)(QUOTE.id, AGENT_ID, admin=False)

    [email] = notifier.emails
    assert email.to == CLIENT_FR.email
    assert email.locale is Locale.FR
    assert email.trip == TRIP
    assert email.quote_url == f"{FRONTEND}/quotes/{QUOTE.id}"


async def test_an_admin_resends_any_quote_email():
    notifier = FakeNotifier()

    await resend(notifier)(QUOTE.id, uuid4(), admin=True)

    assert len(notifier.emails) == 1


async def test_another_agent_may_not_resend():
    notifier = FakeNotifier()

    with pytest.raises(PermissionDenied):
        await resend(notifier)(QUOTE.id, uuid4(), admin=False)

    assert notifier.emails == []


async def test_a_missing_quote_is_not_found():
    with pytest.raises(QuoteNotFound):
        await resend(FakeNotifier())(uuid4(), AGENT_ID, admin=True)


async def test_a_deleted_client_is_not_found():
    with pytest.raises(QuoteNotFound):
        await resend(FakeNotifier(), people=FakePeople(AGENT))(QUOTE.id, AGENT_ID, admin=False)


async def test_without_the_trip_the_email_still_goes():
    notifier = FakeNotifier()

    await resend(notifier, FakePlanQuoting(trip=None))(QUOTE.id, AGENT_ID, admin=False)

    assert notifier.emails[0].trip == QuoteTrip(None, None, None, None)


async def test_a_refused_email_raises_email_not_sent():
    with pytest.raises(QuoteEmailNotSent):
        await resend(FakeNotifier(sent=False))(QUOTE.id, AGENT_ID, admin=False)


async def test_a_quote_email_is_resent_at_most_three_times_an_hour():
    notifier = FakeNotifier()
    use_case = resend(notifier)
    for _ in range(3):
        await use_case(QUOTE.id, AGENT_ID, admin=False)

    with pytest.raises(TooManyRequests):
        await use_case(QUOTE.id, uuid4(), admin=True)  # an admin shares the quote's limit

    assert len(notifier.emails) == 3


async def test_a_refused_email_counts_towards_the_limit():
    use_case = resend(FakeNotifier(sent=False))
    for _ in range(3):
        with pytest.raises(QuoteEmailNotSent):
            await use_case(QUOTE.id, AGENT_ID, admin=False)

    with pytest.raises(TooManyRequests):
        await use_case(QUOTE.id, AGENT_ID, admin=False)


async def test_another_agent_does_not_use_up_the_limit():
    notifier = FakeNotifier()
    use_case = resend(notifier)
    for _ in range(5):
        with pytest.raises(PermissionDenied):
            await use_case(QUOTE.id, uuid4(), admin=False)

    await use_case(QUOTE.id, AGENT_ID, admin=False)

    assert len(notifier.emails) == 1
