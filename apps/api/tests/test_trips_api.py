"""GET /me/trips, with the use case on fakes: no database."""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.public import current_user
from novoya_api.main import create_app
from novoya_api.trips.application.dto import PlanSummary
from novoya_api.trips.application.use_cases.list_my_trips import ListMyTrips
from novoya_api.trips.presentation.http.dependencies import get_list_my_trips
from tests.test_planning_api import signed_in_as
from tests.test_trips_list_my_trips import FakePlans, FakeQuotes, FakeWishes, a_wish

CLIENT_ID = uuid4()


@pytest.fixture
def wishes() -> FakeWishes:
    return FakeWishes([])


@pytest.fixture
def plans() -> FakePlans:
    return FakePlans({})


@pytest.fixture
def quotes() -> FakeQuotes:
    return FakeQuotes({})


@pytest.fixture
def app(wishes, plans, quotes):
    app = create_app()
    app.dependency_overrides[get_list_my_trips] = lambda: ListMyTrips(wishes, plans, quotes)
    return app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_without_a_session_returns_401(client):
    assert (await client.get("/me/trips")).status_code == 401


async def test_an_agent_gets_403(app, client):
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.AGENT, uuid4())

    assert (await client.get("/me/trips")).status_code == 403


async def test_a_client_without_wishes_gets_an_empty_list(app, client):
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.CLIENT, CLIENT_ID)

    response = await client.get("/me/trips")

    assert response.status_code == 200
    assert response.json() == []


async def test_a_client_reads_only_their_own_trips(app, client, wishes, plans, quotes):
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.CLIENT, CLIENT_ID)
    wish = a_wish()
    plan = PlanSummary(uuid4(), "quoted")
    quote_id = uuid4()
    wishes.wishes = [wish]
    plans.plans = {wish.wish_id: plan}
    quotes.quotes = {plan.plan_id: quote_id}

    response = await client.get("/me/trips")

    assert response.status_code == 200
    assert wishes.asked_for == [CLIENT_ID]
    assert response.headers["cache-control"] == "private, no-store"
    [trip] = response.json()
    assert trip["wish_id"] == str(wish.wish_id)
    assert trip["status"] == "answered"
    assert trip["plan_id"] == str(plan.plan_id)
    assert trip["plan_status"] == "quoted"
    assert trip["quote_id"] == str(quote_id)
    assert trip["answer_within_days"] == 4  # the setting, so the page never hard-codes it
    assert set(trip) == {
        "wish_id",
        "text",
        "status",
        "country",
        "city",
        "persons",
        "start_date",
        "end_date",
        "created_at",
        "plan_id",
        "plan_status",
        "quote_id",
        "answer_within_days",
    }


async def test_a_wish_without_plan_has_null_plan_and_quote(app, client, wishes):
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.CLIENT, CLIENT_ID)
    wishes.wishes = [a_wish()]

    [trip] = (await client.get("/me/trips")).json()

    assert (trip["plan_id"], trip["plan_status"], trip["quote_id"]) == (None, None, None)
