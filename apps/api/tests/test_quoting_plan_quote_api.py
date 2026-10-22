"""Quote HTTP: GET /agent/plans/{id}/quote, the quote the assigned agent sent, on fakes."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.application.dto import CurrentUserView
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import Email, UserId
from novoya_api.accounts.public import current_user
from novoya_api.main import create_app
from novoya_api.quoting.application.use_cases.get_plan_quote import GetPlanQuote
from novoya_api.quoting.presentation.http.dependencies import get_get_plan_quote
from novoya_api.shared.domain.value_objects import Locale
from tests.quoting_fakes import (
    AGENT_ID,
    CLIENT_ID,
    NOW,
    OTHER_AGENT,
    PLAN_ID,
    FakeQuotes,
    stored_quote,
)

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


def app_with(role: Role | None, user_id: UUID = AGENT_ID):
    app = create_app()
    app.dependency_overrides[get_get_plan_quote] = lambda: GetPlanQuote(FakeQuotes(QUOTE))
    if role is not None:
        app.dependency_overrides[current_user] = lambda: signed_in_as(role, user_id)
    return app


async def call(app, method: str, path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path)


async def test_the_assigned_agent_reads_the_quote_of_the_plan():
    response = await call(app_with(Role.AGENT), "GET", f"/agent/plans/{PLAN_ID}/quote")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(QUOTE.id)
    assert body["number"] == QUOTE.number
    assert body["plan_id"] == str(PLAN_ID)
    assert body["total"] == "1234.50"
    assert body["currency"] == "EUR"
    assert body["locale"] == "fr"
    assert datetime.fromisoformat(body["sent_at"]) == NOW
    assert datetime.fromisoformat(body["valid_until"]) == NOW + timedelta(days=7)


async def test_a_plan_without_a_quote_returns_404():
    app = app_with(Role.AGENT)
    app.dependency_overrides[get_get_plan_quote] = lambda: GetPlanQuote(FakeQuotes())

    response = await call(app, "GET", f"/agent/plans/{PLAN_ID}/quote")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_the_quote_of_an_unknown_plan_returns_404():
    response = await call(app_with(Role.AGENT), "GET", f"/agent/plans/{uuid4()}/quote")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_another_agent_reading_the_quote_of_the_plan_returns_403():
    app = app_with(Role.AGENT, OTHER_AGENT)

    response = await call(app, "GET", f"/agent/plans/{PLAN_ID}/quote")

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_a_client_cannot_read_the_quote_of_a_plan_as_an_agent():
    app = app_with(Role.CLIENT, CLIENT_ID)

    response = await call(app, "GET", f"/agent/plans/{PLAN_ID}/quote")

    assert response.status_code == 403


async def test_reading_the_quote_of_a_plan_without_a_session_returns_401():
    response = await call(app_with(None), "GET", f"/agent/plans/{PLAN_ID}/quote")

    assert response.status_code == 401


def test_the_quote_of_a_plan_is_documented():
    spec = create_app().openapi()
    read = spec["paths"]["/agent/plans/{plan_id}/quote"]["get"]

    assert read["operationId"] == "getPlanQuote"
    schema = read["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"] == "#/components/schemas/Quote"
    for status in ("401", "403", "404"):
        ref = read["responses"][status]["content"]["application/json"]["schema"]["$ref"]
        assert ref == "#/components/schemas/ErrorResponse", status
