"""The agent builds a custom plan over HTTP (#184): the queue flags it, the agent's plan has
the outline, GET /agent/plans/{id}/offers lists what fits and POST .../items adds one."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.public import current_user
from novoya_api.main import create_app
from novoya_api.planning.application.dto import OfferContact, OfferSummary, TripBrief
from novoya_api.planning.application.use_cases.get_agent_plan import GetAgentPlan
from novoya_api.planning.application.use_cases.get_plan import GetPlan
from novoya_api.planning.application.use_cases.list_quote_queue import ListQuoteQueue
from novoya_api.planning.application.use_cases.plan_offers import AddPlanItem, ListPlanOffers
from novoya_api.planning.application.use_cases.take_plan import TakePlan
from novoya_api.planning.domain.plan import Plan
from novoya_api.planning.presentation.http.dependencies import (
    get_add_plan_item,
    get_answer_days,
    get_current_user_id,
    get_get_agent_plan,
    get_get_plan,
    get_list_plan_offers,
    get_list_quote_queue,
    get_take_plan,
)
from tests.test_planning_agent_api import signed_in_as

AGENT_ID = UUID("00000000-0000-0000-0000-0000000000aa")
OTHER_AGENT = UUID("00000000-0000-0000-0000-0000000000ab")
OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")
WISH_ID = UUID("00000000-0000-0000-0000-0000000000a1")
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
WALK_ID = UUID("00000000-0000-0000-0000-0000000000b2")
WALK = OfferSummary(WALK_ID, "activity", "Gorge walk", "All day", (), False, frozenset({2}))
TRIP = TripBrief(
    WISH_ID,
    "Ten of us, a week of hiking",
    "Greece",
    "Chania",
    Decimal("9000.00"),
    "EUR",
    10,
    date(2026, 6, 1),
    date(2026, 6, 4),
)
OUTLINE = "Day 1: Chania\nDay 2: Samaria gorge"


class FakePlans:
    def __init__(self, plan: Plan) -> None:
        self.plan = plan

    async def get(self, plan_id: UUID) -> Plan | None:
        return self.plan if self.plan.id == plan_id else None

    async def list_queue(self, statuses, agent_id, *, limit=50, offset=0) -> list[Plan]:
        return [self.plan] if self.plan.status in statuses else []

    async def save(self, plan: Plan) -> None:
        self.plan = plan

    async def add_item(self, plan: Plan, item_id: UUID) -> None:
        self.plan = plan


class FakeCatalog:
    async def fitting_offers(self, country, city, tags, persons, start, end):
        return [WALK]

    async def summaries_for(self, offer_ids):
        return [WALK] if WALK_ID in offer_ids else []

    async def contacts_for(self, offer_ids):
        return [
            OfferContact(
                WALK_ID, "activity", "Gorge walk", "All day", "Crete Trails", "t@c.gr", None
            )
        ]


class FakeTrips:
    async def for_wish_ids(self, wish_ids):
        return {WISH_ID: TRIP}


class FakeOwners:
    async def owner_id(self, wish_id: UUID) -> UUID | None:
        return OWNER_ID


class FakeUow:
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class FixedClock:
    def now(self) -> datetime:
        return NOW


@pytest.fixture
def plan() -> Plan:
    return Plan.custom_request(WISH_ID, True, "A custom request", OUTLINE, NOW)


@pytest.fixture
def app(plan):
    plans, catalog, trips = FakePlans(plan), FakeCatalog(), FakeTrips()
    app = create_app()
    app.dependency_overrides[get_list_quote_queue] = lambda: ListQuoteQueue(plans, trips)
    app.dependency_overrides[get_take_plan] = lambda: TakePlan(
        plans, catalog, trips, FakeUow(), FixedClock()
    )
    app.dependency_overrides[get_get_agent_plan] = lambda: GetAgentPlan(plans, catalog, trips)
    app.dependency_overrides[get_list_plan_offers] = lambda: ListPlanOffers(plans, catalog, trips)
    app.dependency_overrides[get_add_plan_item] = lambda: AddPlanItem(
        plans, catalog, trips, FakeUow(), FixedClock()
    )
    app.dependency_overrides[get_get_plan] = lambda: GetPlan(plans, catalog, FakeOwners())
    app.dependency_overrides[get_answer_days] = lambda: 2
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.AGENT)
    return app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_the_queue_flags_a_custom_request(plan, client):
    response = await client.get("/agent/plans")

    [entry] = response.json()
    assert entry["id"] == str(plan.id)
    assert entry["custom"] is True
    assert "outline" not in entry


async def test_the_agent_who_takes_it_sees_the_outline_and_no_item(plan, client):
    response = await client.post(f"/agent/plans/{plan.id}/take")

    body = response.json()
    assert body["custom"] is True
    assert body["outline"] == OUTLINE
    assert body["items"] == []
    assert body["ready_to_quote"] is False


async def test_the_agent_lists_the_offers_that_fit(plan, client):
    await client.post(f"/agent/plans/{plan.id}/take")

    response = await client.get(f"/agent/plans/{plan.id}/offers")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(WALK_ID),
            "kind": "activity",
            "title": "Gorge walk",
            "description": "All day",
            "partner_name": "Crete Trails",
            "open_days": [2],
        }
    ]


async def test_the_agent_adds_an_offer_and_gets_the_plan_back(plan, client):
    await client.post(f"/agent/plans/{plan.id}/take")

    response = await client.post(
        f"/agent/plans/{plan.id}/items",
        json={"offer_id": str(WALK_ID), "day": 2, "note": "  Early start  "},
    )

    assert response.status_code == 201
    [item] = response.json()["items"]
    assert item["offer_id"] == str(WALK_ID)
    assert (item["day"], item["quantity"], item["note"]) == (2, 1, "Early start")
    assert item["negotiated_price"] is None
    assert item["partner_name"] == "Crete Trails"


async def test_an_offer_closed_that_day_is_422(plan, client):
    await client.post(f"/agent/plans/{plan.id}/take")

    response = await client.post(
        f"/agent/plans/{plan.id}/items", json={"offer_id": str(WALK_ID), "day": 3}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_plan"


async def test_adding_before_taking_is_409(plan, client):
    response = await client.post(
        f"/agent/plans/{plan.id}/items", json={"offer_id": str(WALK_ID), "day": 2}
    )

    assert response.status_code == 409


async def test_another_agent_cannot_list_or_add(plan, app, client):
    await client.post(f"/agent/plans/{plan.id}/take")
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.AGENT, OTHER_AGENT)

    offers = await client.get(f"/agent/plans/{plan.id}/offers")
    added = await client.post(
        f"/agent/plans/{plan.id}/items", json={"offer_id": str(WALK_ID), "day": 2}
    )

    assert (offers.status_code, added.status_code) == (403, 403)


async def test_a_client_cannot_add_items(plan, app, client):
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.CLIENT)

    response = await client.post(
        f"/agent/plans/{plan.id}/items", json={"offer_id": str(WALK_ID), "day": 2}
    )

    assert response.status_code == 403


async def test_the_client_sees_a_custom_plan_without_the_outline(plan, app, client):
    app.dependency_overrides[get_current_user_id] = lambda: OWNER_ID

    response = await client.get(f"/plans/{plan.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["custom"] is True
    assert body["status"] == "requested"
    assert body["items"] == []
    assert "outline" not in body
    assert OUTLINE not in response.text
