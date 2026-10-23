"""POST /wishes is tested with the use case built on fakes: no database, no model."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import Email, UserId
from novoya_api.accounts.public import CurrentUserView, current_user
from novoya_api.main import create_app
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.wishes.application.ports.destination_reader import DestinationReading
from novoya_api.wishes.application.use_cases.send_wish import SEND_LIMIT, SEND_WINDOW, SendWish
from novoya_api.wishes.domain.wish import Destination
from novoya_api.wishes.infrastructure.llm.destination_reader import NameMatchingReader
from novoya_api.wishes.infrastructure.llm.panel_builder import TagsFromOffersBuilder
from novoya_api.wishes.presentation.http import dependencies
from novoya_api.wishes.presentation.http.dependencies import get_current_user_id, get_send_wish
from tests.accounts.fakes import FrozenClock

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_USER_ID = UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


LISBON = Destination("Portugal", "Lisbon")

TAGS = {
    LISBON: ["style:beach", "style:culture", "rhythm:calm", "food:seafood"],
    Destination("Portugal", "Porto"): ["style:culture", "style:city", "food:wine"],
    Destination("Morocco", "Marrakech"): ["style:culture", "style:desert", "accommodation:riad"],
}


class FakeCatalog:
    async def covered_destinations(self) -> list[Destination]:
        return list(TAGS)

    async def tags_at(self, destination: Destination) -> list[str]:
        return list(TAGS.get(destination, []))


class FakeReader:
    def __init__(self) -> None:
        self.reading = DestinationReading(destination=None, suggestions=[])

    async def read(self, text, covered) -> DestinationReading:
        return self.reading


class FakeWishes:
    def __init__(self) -> None:
        self.added = []

    async def add(self, wish) -> None:
        self.added.append(wish)


class FakeUnitOfWork:
    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


@pytest.fixture
def reader() -> FakeReader:
    return FakeReader()


@pytest.fixture
def wishes() -> FakeWishes:
    return FakeWishes()


@pytest.fixture
def limiter_clock() -> FrozenClock:
    return FrozenClock()


@pytest.fixture
def limiter(limiter_clock) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(limiter_clock)


@pytest.fixture
def app(reader, wishes, limiter):
    app = create_app()
    send_wish = SendWish(
        wishes=wishes,
        catalog=FakeCatalog(),
        reader=reader,
        panel_builder=TagsFromOffersBuilder(),
        rate_limiter=limiter,
        uow=FakeUnitOfWork(),
        clock=FixedClock(),
    )
    app.dependency_overrides[get_send_wish] = lambda: send_wish
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    return app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_covered_wish_returns_201_with_the_panel(reader, wishes, client):
    reader.reading = DestinationReading(destination=LISBON, suggestions=[])

    response = await client.post("/wishes", json={"text": "A week in Lisbon"})

    assert response.status_code == 201
    body = response.json()
    assert UUID(body["id"]) == wishes.added[0].id
    assert body["status"] == "panel_shown"
    assert body["destination"] == {"country": "Portugal", "city": "Lisbon"}
    assert body["panel"] == wishes.added[0].panel.to_dict()
    assert body["panel"]["sections"]
    assert body["suggestions"] == []


async def test_wish_is_saved_for_the_current_user(reader, wishes, client):
    reader.reading = DestinationReading(destination=LISBON, suggestions=[])

    await client.post("/wishes", json={"text": "A week in Lisbon"})

    assert [wish.user_id for wish in wishes.added] == [USER_ID]


async def test_uncovered_wish_returns_201_with_suggestions_and_no_panel(reader, client):
    reader.reading = DestinationReading(
        destination=Destination("Spain", "Madrid"), suggestions=[LISBON]
    )

    response = await client.post("/wishes", json={"text": "A week in Madrid"})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "not_covered"
    assert body["destination"] == {"country": "Spain", "city": "Madrid"}
    assert body["panel"] is None
    assert body["suggestions"] == [{"country": "Portugal", "city": "Lisbon"}]


async def test_wish_without_destination_returns_a_draft_and_every_covered_destination(client):
    covered = list(TAGS)

    response = await client.post("/wishes", json={"text": "Somewhere warm"})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["destination"] is None
    assert body["panel"] is None
    assert body["suggestions"] == [{"country": d.country, "city": d.city} for d in covered]


async def test_text_of_1000_characters_is_accepted(client):
    response = await client.post("/wishes", json={"text": "a" * 1000})

    assert response.status_code == 201


@pytest.mark.parametrize(
    "text",
    ["", "   ", "a" * 1001, "Lisbon\u0000", "Lisbon\u0007 in May"],
    ids=["empty", "blank", "too_long", "nul", "control"],
)
async def test_invalid_text_returns_422(wishes, client, text):
    response = await client.post("/wishes", json={"text": text})

    assert response.status_code == 422
    assert wishes.added == []


async def test_missing_text_returns_422(client):
    response = await client.post("/wishes", json={})

    assert response.status_code == 422


async def test_without_a_signed_in_user_returns_401(app, wishes, client):
    del app.dependency_overrides[get_current_user_id]

    response = await client.post("/wishes", json={"text": "A week in Lisbon"})

    assert response.status_code == 401
    assert wishes.added == []


def test_send_wish_route_is_documented(app):
    operation = app.openapi()["paths"]["/wishes"]["post"]

    assert operation["operationId"] == "sendWish"
    assert operation["tags"] == ["wishes"]
    assert "201" in operation["responses"]


def test_without_an_api_key_the_reader_and_builder_skip_the_model(monkeypatch):
    def no_key(**kwargs):
        raise LLMError("NOVOYA_OPENROUTER_API_KEY is not set")

    monkeypatch.setattr(dependencies, "get_orchestrator", no_key)

    assert isinstance(dependencies.get_destination_reader(), NameMatchingReader)
    assert isinstance(dependencies.get_panel_builder(), TagsFromOffersBuilder)


def signed_in_as(role: Role) -> CurrentUserView:
    return CurrentUserView(
        user_id=UserId(USER_ID),
        email=Email("someone@example.com"),
        name=None,
        role=role,
        locale=Locale.EN,
        session_id=USER_ID,
    )


@pytest.mark.parametrize(
    ("role", "status"), [(Role.CLIENT, 201), (Role.ADMIN, 201), (Role.AGENT, 403)]
)
async def test_only_clients_and_admins_send_wishes(app, wishes, client, role, status):
    del app.dependency_overrides[get_current_user_id]
    app.dependency_overrides[current_user] = lambda: signed_in_as(role)

    response = await client.post("/wishes", json={"text": "A week in Lisbon"})

    assert response.status_code == status
    assert [wish.user_id for wish in wishes.added] == ([USER_ID] if status == 201 else [])


def test_send_wish_documents_the_shared_error_responses(app):
    schema = app.openapi()
    responses = schema["paths"]["/wishes"]["post"]["responses"]

    for status in ("401", "403", "422"):
        ref = responses[status]["content"]["application/json"]["schema"]["$ref"]
        assert ref == "#/components/schemas/ErrorResponse", status


def test_send_wish_reads_the_catalog_through_the_request_session():
    session = object()

    limiter = dependencies.get_rate_limiter()
    use_case = dependencies.get_send_wish(
        session=session,
        reader=NameMatchingReader(),
        panel_builder=TagsFromOffersBuilder(),
        rate_limiter=limiter,
    )

    assert use_case._catalog._session is session
    assert use_case._wishes._session is session
    assert use_case._uow._session is session
    assert use_case._rate_limiter is limiter


# Rate limit


async def test_past_the_limit_returns_429_with_retry_after(app, wishes, client):
    for _ in range(SEND_LIMIT):
        assert (await client.post("/wishes", json={"text": "A week in Lisbon"})).status_code == 201

    response = await client.post("/wishes", json={"text": "A week in Lisbon"})

    assert response.status_code == 429
    assert response.json() == {
        "code": "too_many_requests",
        "detail": f"try again in {int(SEND_WINDOW.total_seconds())} seconds",
    }
    assert response.headers["Retry-After"] == str(int(SEND_WINDOW.total_seconds()))
    assert len(wishes.added) == SEND_LIMIT


async def test_another_client_still_sends_wishes_when_one_is_limited(app, client):
    for _ in range(SEND_LIMIT + 1):
        await client.post("/wishes", json={"text": "A week in Lisbon"})
    app.dependency_overrides[get_current_user_id] = lambda: OTHER_USER_ID

    response = await client.post("/wishes", json={"text": "A week in Lisbon"})

    assert response.status_code == 201


def test_send_wish_documents_429(app):
    responses = app.openapi()["paths"]["/wishes"]["post"]["responses"]

    ref = responses["429"]["content"]["application/json"]["schema"]["$ref"]
    assert ref == "#/components/schemas/ErrorResponse"


def test_the_wishes_rate_limiter_is_built_once():
    assert dependencies.get_rate_limiter() is dependencies.get_rate_limiter()
