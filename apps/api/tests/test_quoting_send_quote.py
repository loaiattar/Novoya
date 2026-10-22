"""SendQuote and GetQuotePdf, tested with fake ports: no database, no PDF engine."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from novoya_api.planning.domain.errors import PlanNotReady
from novoya_api.quoting.application.dto import QuotePdf
from novoya_api.quoting.application.use_cases.get_quote_pdf import GetQuotePdf
from novoya_api.quoting.application.use_cases.send_quote import SendQuote
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.shared.domain.value_objects import Locale
from tests.quoting_fakes import (
    AGENT,
    AGENT_ID,
    CLIENT_EN,
    CLIENT_FR,
    CLIENT_ID,
    FRONTEND,
    NOW,
    OTHER_CLIENT,
    PLAN_ID,
    QUOTED,
    TRIP,
    FakeNotifier,
    FakePeople,
    FakePlanQuoting,
    FakeQuotes,
    FakeRenderer,
    FakeUow,
    FixedClock,
    stored_quote,
)


class Sending:
    def __init__(
        self, plans: FakePlanQuoting | None = None, client=CLIENT_FR, email_sent: bool = True
    ) -> None:
        self.plans = plans or FakePlanQuoting()
        self.renderer = FakeRenderer()
        self.quotes = FakeQuotes()
        self.uow = FakeUow()
        self.notifier = FakeNotifier(email_sent, self.uow)
        self.use_case = SendQuote(
            self.plans,
            FakePeople(client, AGENT),
            self.renderer,
            self.quotes,
            self.notifier,
            self.uow,
            FixedClock(),
            FRONTEND,
        )


async def test_sending_returns_the_issued_quote():
    sending = Sending()

    view = await sending.use_case(PLAN_ID, AGENT_ID)

    assert view.id == sending.quotes.added[0].id
    assert view.number == sending.quotes.added[0].number
    assert view.plan_id == PLAN_ID
    assert view.total == Decimal("1234.50")
    assert view.currency == "EUR"
    assert view.sent_at == NOW
    assert view.valid_until == NOW + timedelta(days=7)


async def test_sending_quotes_the_plan_as_the_agent():
    sending = Sending()

    await sending.use_case(PLAN_ID, AGENT_ID)

    assert sending.plans.calls == [(PLAN_ID, AGENT_ID)]


async def test_the_quote_is_in_the_clients_language():
    sending = Sending(client=CLIENT_FR)

    view = await sending.use_case(PLAN_ID, AGENT_ID)

    assert view.locale == "fr"
    assert sending.quotes.added[0].locale is Locale.FR


async def test_an_english_client_gets_an_english_quote():
    sending = Sending(client=CLIENT_EN)

    view = await sending.use_case(PLAN_ID, AGENT_ID)

    assert view.locale == "en"


async def test_the_quote_is_saved_with_its_pdf_and_committed():
    sending = Sending()

    await sending.use_case(PLAN_ID, AGENT_ID)

    [quote] = sending.quotes.added
    assert quote.pdf == b"%PDF-1.7 fake"
    assert (quote.plan_id, quote.client_id, quote.agent_id) == (PLAN_ID, CLIENT_ID, AGENT_ID)
    assert sending.uow.commits == 1


async def test_the_pdf_is_rendered_from_the_plan_and_the_people():
    sending = Sending()

    await sending.use_case(PLAN_ID, AGENT_ID)

    [document] = sending.renderer.documents
    assert document.quote is sending.quotes.added[0]
    assert document.plan == QUOTED
    assert document.client == CLIENT_FR
    assert document.agent == AGENT


async def test_the_pdf_links_to_the_quote_in_the_app():
    sending = Sending()

    await sending.use_case(PLAN_ID, AGENT_ID)

    [document] = sending.renderer.documents
    assert document.answer_url == f"{FRONTEND}/quotes/{document.quote.id}"


async def test_a_plan_that_is_not_ready_sends_nothing():
    sending = Sending(FakePlanQuoting(PlanNotReady("an item has no price")))

    with pytest.raises(PlanNotReady):
        await sending.use_case(PLAN_ID, AGENT_ID)

    assert sending.quotes.added == []
    assert sending.renderer.documents == []
    assert sending.uow.commits == 0
    assert sending.notifier.emails == []


async def test_the_client_gets_an_email_after_the_commit():
    sending = Sending()

    view = await sending.use_case(PLAN_ID, AGENT_ID)

    [email] = sending.notifier.emails
    assert sending.notifier.commits_before == [1]
    assert (email.to, email.name) == (CLIENT_FR.email, CLIENT_FR.name)
    assert email.trip == TRIP
    assert email.quote_url == f"{FRONTEND}/quotes/{view.id}"
    assert view.email_sent is True


async def test_the_email_is_in_the_quotes_language():
    sending = Sending(client=CLIENT_FR)

    await sending.use_case(PLAN_ID, AGENT_ID, Locale.EN)

    assert sending.notifier.emails[0].locale is Locale.EN


async def test_a_failed_email_keeps_the_quote():
    sending = Sending(email_sent=False)

    view = await sending.use_case(PLAN_ID, AGENT_ID)

    assert view.email_sent is False
    assert sending.uow.commits == 1
    assert sending.quotes.added[0].id == view.id


async def test_the_client_reads_their_quote_pdf():
    quote = stored_quote()

    pdf = await GetQuotePdf(FakeQuotes(quote))(quote.id, CLIENT_ID, staff=False)

    assert pdf == QuotePdf(f"{quote.number}.pdf", b"%PDF-1.7 stored")


async def test_staff_read_any_quote_pdf():
    quote = stored_quote()

    pdf = await GetQuotePdf(FakeQuotes(quote))(quote.id, AGENT_ID, staff=True)

    assert pdf.content == b"%PDF-1.7 stored"


async def test_another_client_cannot_read_the_quote_pdf():
    quote = stored_quote()

    with pytest.raises(QuoteNotFound):
        await GetQuotePdf(FakeQuotes(quote))(quote.id, OTHER_CLIENT, staff=False)


async def test_a_missing_quote_pdf_is_not_found():
    with pytest.raises(QuoteNotFound):
        await GetQuotePdf(FakeQuotes(stored_quote()))(uuid4(), CLIENT_ID, staff=True)


async def test_the_agent_can_send_the_quote_in_english_to_a_french_client():
    sending = Sending(client=CLIENT_FR)

    view = await sending.use_case(PLAN_ID, AGENT_ID, Locale.EN)

    assert view.locale == "en"
    assert sending.quotes.added[0].locale is Locale.EN
    assert sending.renderer.documents[0].quote.locale is Locale.EN


async def test_the_agent_can_send_the_quote_in_french_to_an_english_client():
    sending = Sending(client=CLIENT_EN)

    view = await sending.use_case(PLAN_ID, AGENT_ID, Locale.FR)

    assert view.locale == "fr"
