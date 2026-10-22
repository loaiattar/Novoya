"""Quote HTTP on fakes: send the quote, read it, download its PDF."""

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.application.dto import CurrentUserView
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import Email, UserId
from novoya_api.accounts.public import current_user
from novoya_api.main import create_app
from novoya_api.planning.domain.errors import PlanNotReady
from novoya_api.quoting.application.use_cases.answer_quote import AnswerQuote
from novoya_api.quoting.application.use_cases.get_quote import GetQuote
from novoya_api.quoting.application.use_cases.get_quote_pdf import GetQuotePdf
from novoya_api.quoting.application.use_cases.resend_quote_email import ResendQuoteEmail
from novoya_api.quoting.application.use_cases.send_quote import SendQuote
from novoya_api.quoting.domain.quote import Quote, QuoteStatus
from novoya_api.quoting.presentation.http.dependencies import (
    get_answer_quote,
    get_get_quote,
    get_get_quote_pdf,
    get_resend_quote_email,
    get_send_quote,
)
from novoya_api.shared.domain.errors import InvalidTransition, PermissionDenied
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from tests.quoting_fakes import (
    AGENT,
    AGENT_ID,
    CLIENT_FR,
    CLIENT_ID,
    FRONTEND,
    NOW,
    OTHER_CLIENT,
    PLAN_ID,
    FakeNotifier,
    FakePeople,
    FakePlanQuoting,
    FakeQuotes,
    FakeRenderer,
    FakeUow,
    FixedClock,
    stored_quote,
)

ADMIN_ID = UUID("00000000-0000-0000-0000-0000000000ad")
QUOTE = stored_quote()


def signed_in_as(role: Role, user_id: UUID = AGENT_ID) -> CurrentUserView:
    return CurrentUserView(
        user_id=UserId(user_id),
        email=Email("someone@example.com"),
        name=None,
        role=role,
        locale=Locale.EN,
        session_id=user_id,
    )


def app_with(
    plans: FakePlanQuoting,
    role: Role | None,
    user_id: UUID = AGENT_ID,
    email_sent: bool = True,
    quote: Quote = QUOTE,
):
    quotes = FakeQuotes(quote)
    app = create_app()
    app.dependency_overrides[get_send_quote] = lambda: SendQuote(
        plans,
        FakePeople(CLIENT_FR, AGENT),
        FakeRenderer(),
        quotes,
        FakeNotifier(),
        FakeUow(),
        FixedClock(),
        FRONTEND,
    )
    people = FakePeople(CLIENT_FR, AGENT)
    app.dependency_overrides[get_get_quote] = lambda: GetQuote(quotes, plans, people, FixedClock())
    app.dependency_overrides[get_answer_quote] = lambda: AnswerQuote(
        quotes, plans, FakeUow(), FixedClock()
    )
    app.dependency_overrides[get_get_quote_pdf] = lambda: GetQuotePdf(quotes)
    limiter = InMemoryRateLimiter(FixedClock())  # one per app: tests don't share counters
    app.dependency_overrides[get_resend_quote_email] = lambda: ResendQuoteEmail(
        quotes, plans, FakePeople(CLIENT_FR, AGENT), FakeNotifier(email_sent), limiter, FRONTEND
    )
    if role is not None:
        app.dependency_overrides[current_user] = lambda: signed_in_as(role, user_id)
    return app


async def call(app, method: str, path: str, body: dict | None = None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, json=body)


@pytest.fixture
async def agent() -> AsyncIterator[AsyncClient]:
    app = app_with(FakePlanQuoting(), Role.AGENT)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_the_agent_sends_the_quote(agent):
    response = await agent.post(f"/agent/plans/{PLAN_ID}/quote")

    assert response.status_code == 201
    body = response.json()
    assert body["plan_id"] == str(PLAN_ID)
    assert body["number"].startswith("NV-20261019-")
    assert body["total"] == "1234.50"
    assert body["currency"] == "EUR"
    assert body["locale"] == "fr"
    assert datetime.fromisoformat(body["sent_at"]) == NOW
    assert datetime.fromisoformat(body["valid_until"]) == NOW + timedelta(days=7)
    assert body["email_sent"] is True
    assert UUID(body["id"])


async def test_a_plan_not_ready_returns_422_plan_not_ready():
    app = app_with(FakePlanQuoting(PlanNotReady("an item has no price")), Role.AGENT)

    response = await call(app, "POST", f"/agent/plans/{PLAN_ID}/quote")

    assert response.status_code == 422
    assert response.json()["code"] == "plan_not_ready"


async def test_quoting_a_plan_not_being_negotiated_returns_409():
    app = app_with(FakePlanQuoting(InvalidTransition("not negotiating")), Role.AGENT)

    response = await call(app, "POST", f"/agent/plans/{PLAN_ID}/quote")

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"


async def test_another_agent_quoting_the_plan_returns_403():
    app = app_with(FakePlanQuoting(PermissionDenied("not yours")), Role.AGENT)

    response = await call(app, "POST", f"/agent/plans/{PLAN_ID}/quote")

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_a_client_cannot_send_a_quote():
    app = app_with(FakePlanQuoting(), Role.CLIENT, CLIENT_ID)

    response = await call(app, "POST", f"/agent/plans/{PLAN_ID}/quote")

    assert response.status_code == 403


async def test_sending_a_quote_without_a_session_returns_401():
    app = app_with(FakePlanQuoting(), None)

    response = await call(app, "POST", f"/agent/plans/{PLAN_ID}/quote")

    assert response.status_code == 401


async def test_the_client_downloads_their_quote_pdf():
    app = app_with(FakePlanQuoting(), Role.CLIENT, CLIENT_ID)

    response = await call(app, "GET", f"/quotes/{QUOTE.id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert f"{QUOTE.number}.pdf" in response.headers["content-disposition"]
    assert response.content == b"%PDF-1.7 stored"


@pytest.mark.parametrize(("role", "user_id"), [(Role.AGENT, AGENT_ID), (Role.ADMIN, ADMIN_ID)])
async def test_staff_download_any_quote_pdf(role, user_id):
    app = app_with(FakePlanQuoting(), role, user_id)

    response = await call(app, "GET", f"/quotes/{QUOTE.id}/pdf")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.7 stored"


async def test_another_client_gets_404_for_the_quote_pdf():
    app = app_with(FakePlanQuoting(), Role.CLIENT, OTHER_CLIENT)

    response = await call(app, "GET", f"/quotes/{QUOTE.id}/pdf")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_a_missing_quote_pdf_returns_404():
    app = app_with(FakePlanQuoting(), Role.CLIENT, CLIENT_ID)

    response = await call(app, "GET", f"/quotes/{uuid4()}/pdf")

    assert response.status_code == 404


async def test_downloading_a_quote_pdf_without_a_session_returns_401():
    app = app_with(FakePlanQuoting(), None)

    response = await call(app, "GET", f"/quotes/{QUOTE.id}/pdf")

    assert response.status_code == 401


async def test_the_agent_chooses_the_language_of_the_quote(agent):
    response = await agent.post(f"/agent/plans/{PLAN_ID}/quote", json={"locale": "en"})

    assert response.status_code == 201
    assert response.json()["locale"] == "en"


async def test_without_a_language_the_quote_is_in_the_clients(agent):
    response = await agent.post(f"/agent/plans/{PLAN_ID}/quote", json={})

    assert response.status_code == 201
    assert response.json()["locale"] == "fr"


async def test_an_unknown_language_is_refused(agent):
    response = await agent.post(f"/agent/plans/{PLAN_ID}/quote", json={"locale": "de"})

    assert response.status_code == 422


async def test_the_agent_who_sent_the_quote_resends_its_email():
    app = app_with(FakePlanQuoting(), Role.AGENT, AGENT_ID)

    response = await call(app, "POST", f"/agent/quotes/{QUOTE.id}/email")

    assert response.status_code == 204


@pytest.mark.parametrize(("role", "user_id"), [(Role.ADMIN, ADMIN_ID), (Role.SUPER_ADMIN, uuid4())])
async def test_an_admin_resends_any_quote_email(role, user_id):
    app = app_with(FakePlanQuoting(), role, user_id)

    response = await call(app, "POST", f"/agent/quotes/{QUOTE.id}/email")

    assert response.status_code == 204


async def test_another_agent_cannot_resend_the_quote_email():
    app = app_with(FakePlanQuoting(), Role.AGENT, uuid4())

    response = await call(app, "POST", f"/agent/quotes/{QUOTE.id}/email")

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_a_client_cannot_resend_the_quote_email():
    app = app_with(FakePlanQuoting(), Role.CLIENT, CLIENT_ID)

    response = await call(app, "POST", f"/agent/quotes/{QUOTE.id}/email")

    assert response.status_code == 403


async def test_resending_without_a_session_returns_401():
    app = app_with(FakePlanQuoting(), None)

    response = await call(app, "POST", f"/agent/quotes/{QUOTE.id}/email")

    assert response.status_code == 401


async def test_resending_the_email_of_a_missing_quote_returns_404():
    app = app_with(FakePlanQuoting(), Role.ADMIN, ADMIN_ID)

    response = await call(app, "POST", f"/agent/quotes/{uuid4()}/email")

    assert response.status_code == 404


async def test_an_email_server_that_refuses_returns_503_email_not_sent():
    app = app_with(FakePlanQuoting(), Role.AGENT, AGENT_ID, email_sent=False)

    response = await call(app, "POST", f"/agent/quotes/{QUOTE.id}/email")

    assert response.status_code == 503
    assert response.json()["code"] == "email_not_sent"


async def test_a_fourth_resend_in_an_hour_returns_429():
    app = app_with(FakePlanQuoting(), Role.AGENT, AGENT_ID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(3):
            assert (await client.post(f"/agent/quotes/{QUOTE.id}/email")).status_code == 204
        response = await client.post(f"/agent/quotes/{QUOTE.id}/email")

    assert response.status_code == 429
    assert response.json()["code"] == "too_many_requests"
    assert int(response.headers["Retry-After"]) > 0


async def test_the_client_reads_their_quote():
    app = app_with(FakePlanQuoting(), Role.CLIENT, CLIENT_ID)

    response = await call(app, "GET", f"/quotes/{QUOTE.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(QUOTE.id)
    assert body["number"] == QUOTE.number
    assert body["plan_id"] == str(PLAN_ID)
    assert body["total"] == "1234.50"
    assert body["currency"] == "EUR"
    assert body["locale"] == "fr"
    assert datetime.fromisoformat(body["valid_until"]) == NOW + timedelta(days=7)
    assert body["status"] == "open"
    assert "email_sent" not in body
    assert body["agent_name"] == AGENT.name
    assert (body["city"], body["persons"], body["budget_max"]) == ("Chania", 2, "1500.00")
    assert body["items"][0] == {
        "day": 1,
        "kind": "hotel",
        "title": "Sea view room",
        "description": "Rooms over the bay",
        "quantity": 6,
        "price": "900.00",
    }
    assert body["extras"][1] == {"label": "Breakfast", "unit": "", "price": None}
    assert (body["decided_at"], body["client_comment"]) == (None, None)
    assert response.headers["Cache-Control"] == "private, no-store"


async def test_the_quote_shows_the_clients_answer():
    answered = stored_quote(QuoteStatus.ACCEPTED)
    app = app_with(FakePlanQuoting(), Role.CLIENT, CLIENT_ID, quote=answered)

    response = await call(app, "GET", f"/quotes/{answered.id}")

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


@pytest.mark.parametrize(("role", "user_id"), [(Role.AGENT, AGENT_ID), (Role.ADMIN, ADMIN_ID)])
async def test_staff_read_any_quote(role, user_id):
    app = app_with(FakePlanQuoting(), role, user_id)

    response = await call(app, "GET", f"/quotes/{QUOTE.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(QUOTE.id)


async def test_another_client_gets_404_for_the_quote():
    app = app_with(FakePlanQuoting(), Role.CLIENT, OTHER_CLIENT)

    response = await call(app, "GET", f"/quotes/{QUOTE.id}")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_a_missing_quote_returns_404():
    app = app_with(FakePlanQuoting(), Role.CLIENT, CLIENT_ID)

    response = await call(app, "GET", f"/quotes/{uuid4()}")

    assert response.status_code == 404


async def test_reading_a_quote_without_a_session_returns_401():
    app = app_with(FakePlanQuoting(), None)

    response = await call(app, "GET", f"/quotes/{QUOTE.id}")

    assert response.status_code == 401


@pytest.mark.parametrize(("action", "status"), [("accept", "accepted"), ("reject", "rejected")])
async def test_the_client_answers_their_quote(action, status):
    plans = FakePlanQuoting()
    quote = stored_quote()
    app = app_with(plans, Role.CLIENT, CLIENT_ID, quote=quote)

    response = await call(app, "POST", f"/quotes/{quote.id}/{action}", {"comment": "Hi"})

    assert response.status_code == 204
    assert plans.answers == [(PLAN_ID, action == "accept")]
    read = (await call(app, "GET", f"/quotes/{quote.id}")).json()
    assert (read["status"], read["client_comment"]) == (status, "Hi")
    assert read["decided_at"] is not None


async def test_an_answer_needs_no_body():
    quote = stored_quote()
    app = app_with(FakePlanQuoting(), Role.CLIENT, CLIENT_ID, quote=quote)

    response = await call(app, "POST", f"/quotes/{quote.id}/accept")

    assert response.status_code == 204


async def test_a_second_answer_returns_409():
    quote = stored_quote(QuoteStatus.ACCEPTED)
    app = app_with(FakePlanQuoting(), Role.CLIENT, CLIENT_ID, quote=quote)

    response = await call(app, "POST", f"/quotes/{quote.id}/reject")

    assert response.status_code == 409
    assert response.json()["code"] == "quote_answered"


async def test_an_agent_cannot_answer_for_the_client():
    quote = stored_quote()
    app = app_with(FakePlanQuoting(), Role.AGENT, AGENT_ID, quote=quote)

    response = await call(app, "POST", f"/quotes/{quote.id}/accept")

    assert response.status_code == 403


async def test_another_client_gets_404_when_answering():
    quote = stored_quote()
    app = app_with(FakePlanQuoting(), Role.CLIENT, OTHER_CLIENT, quote=quote)

    response = await call(app, "POST", f"/quotes/{quote.id}/accept")

    assert response.status_code == 404


async def test_a_too_long_comment_returns_422():
    quote = stored_quote()
    app = app_with(FakePlanQuoting(), Role.CLIENT, CLIENT_ID, quote=quote)

    response = await call(app, "POST", f"/quotes/{quote.id}/accept", {"comment": "x" * 1001})

    assert response.status_code == 422


async def test_answering_without_a_session_returns_401():
    app = app_with(FakePlanQuoting(), None)

    response = await call(app, "POST", f"/quotes/{QUOTE.id}/accept")

    assert response.status_code == 401
