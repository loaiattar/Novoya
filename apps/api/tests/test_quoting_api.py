"""Quote HTTP: POST /agent/plans/{id}/quote and GET /quotes/{id}/pdf, on fakes."""

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
from novoya_api.quoting.application.use_cases.get_quote_pdf import GetQuotePdf
from novoya_api.quoting.application.use_cases.send_quote import SendQuote
from novoya_api.quoting.presentation.http.dependencies import get_get_quote_pdf, get_send_quote
from novoya_api.shared.domain.errors import InvalidTransition, PermissionDenied
from novoya_api.shared.domain.value_objects import Locale
from tests.quoting_fakes import (
    AGENT,
    AGENT_ID,
    CLIENT_FR,
    CLIENT_ID,
    FRONTEND,
    NOW,
    OTHER_CLIENT,
    PLAN_ID,
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


def app_with(plans: FakePlanQuoting, role: Role | None, user_id: UUID = AGENT_ID):
    quotes = FakeQuotes(QUOTE)
    app = create_app()
    app.dependency_overrides[get_send_quote] = lambda: SendQuote(
        plans,
        FakePeople(CLIENT_FR, AGENT),
        FakeRenderer(),
        quotes,
        FakeUow(),
        FixedClock(),
        FRONTEND,
    )
    app.dependency_overrides[get_get_quote_pdf] = lambda: GetQuotePdf(quotes)
    if role is not None:
        app.dependency_overrides[current_user] = lambda: signed_in_as(role, user_id)
    return app


async def call(app, method: str, path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path)


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
