"""Advisor chat HTTP on fakes (#169): who may read and write the conversation of a wish."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.application.dto import CurrentUserView
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import Email, UserId
from novoya_api.accounts.public import current_user
from novoya_api.main import create_app
from novoya_api.messaging.application.use_cases.list_messages import ListMessages
from novoya_api.messaging.application.use_cases.post_message import (
    POST_LIMIT,
    POST_WINDOW,
    PostMessage,
)
from novoya_api.messaging.domain.message import Message, Side, WishPlan
from novoya_api.messaging.presentation.http.dependencies import (
    get_list_messages,
    get_post_message,
)
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter

NOW = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)
WISH_ID = UUID("00000000-0000-0000-0000-00000000a001")
CLIENT_ID = UUID("00000000-0000-0000-0000-0000000000c1")
OTHER_CLIENT_ID = UUID("00000000-0000-0000-0000-0000000000c2")
AGENT_ID = UUID("00000000-0000-0000-0000-0000000000a9")
OTHER_AGENT_ID = UUID("00000000-0000-0000-0000-0000000000a8")
ADMIN_ID = UUID("00000000-0000-0000-0000-0000000000ad")

QUEUED = [WishPlan("requested", None)]
TAKEN = [WishPlan("negotiating", AGENT_ID)]
PROPOSED = [WishPlan("proposed", None)]


class FakeMessages:
    def __init__(self) -> None:
        self.stored: list[Message] = []

    async def list_for_wish(self, wish_id: UUID) -> list[Message]:
        return [m for m in self.stored if m.wish_id == wish_id]

    async def add(self, message: Message) -> None:
        self.stored.append(message)


class FakeWishes:
    async def owner_id(self, wish_id: UUID) -> UUID | None:
        return CLIENT_ID if wish_id == WISH_ID else None


class FakePlans:
    def __init__(self, plans: list[WishPlan]) -> None:
        self.plans = plans

    async def of_wish(self, wish_id: UUID) -> list[WishPlan]:
        return self.plans if wish_id == WISH_ID else []


class FakeUow:
    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class FixedClock:
    def now(self) -> datetime:
        return NOW


def post_message(messages: FakeMessages, plans: list[WishPlan], limiter=None) -> PostMessage:
    return PostMessage(
        messages,
        FakeWishes(),
        FakePlans(plans),
        FakeUow(),
        FixedClock(),
        limiter or InMemoryRateLimiter(FixedClock()),
    )


def app_for(role: Role | None, user_id: UUID, messages: FakeMessages, plans=()):
    plans = list(plans)
    limiter = InMemoryRateLimiter(FixedClock())  # one per app: tests don't share counters
    app = create_app()
    app.dependency_overrides[get_list_messages] = lambda: ListMessages(
        messages, FakeWishes(), FakePlans(plans)
    )
    app.dependency_overrides[get_post_message] = lambda: post_message(messages, plans, limiter)
    if role is not None:
        app.dependency_overrides[current_user] = lambda: CurrentUserView(
            user_id=UserId(user_id),
            email=Email("someone@example.com"),
            name=None,
            role=role,
            locale=Locale.EN,
            session_id=user_id,
        )
    return app


async def call(app, method: str, path: str, body: dict | None = None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, json=body)


PATH = f"/wishes/{WISH_ID}/messages"


async def client_says_hello(messages: FakeMessages) -> None:
    await post_message(messages, [])(WISH_ID, CLIENT_ID, Side.CLIENT, "Hello")


async def test_the_client_writes_and_reads_their_conversation():
    messages = FakeMessages()
    app = app_for(Role.CLIENT, CLIENT_ID, messages)

    posted = await call(app, "POST", PATH, {"body": "  Can we add a day in Kyoto?  "})
    listed = await call(app, "GET", PATH)

    assert posted.status_code == 201
    assert posted.json()["body"] == "Can we add a day in Kyoto?"
    assert posted.json()["from_agency"] is False
    assert posted.json()["mine"] is True
    assert datetime.fromisoformat(posted.json()["sent_at"]) == NOW
    assert posted.headers["cache-control"] == "private, no-store"
    assert listed.status_code == 200
    assert [m["body"] for m in listed.json()] == ["Can we add a day in Kyoto?"]
    assert listed.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUPER_ADMIN])
@pytest.mark.parametrize(
    "plans", [[], PROPOSED, QUEUED, TAKEN], ids=["none", "proposed", "queued", "taken"]
)
async def test_admins_always_read_and_answer(role, plans):
    messages = FakeMessages()
    await client_says_hello(messages)
    app = app_for(role, ADMIN_ID, messages, plans)

    answered = await call(app, "POST", PATH, {"body": "Of course!"})
    listed = await call(app, "GET", PATH)

    assert answered.status_code == 201
    assert answered.json()["from_agency"] is True
    assert [(m["body"], m["from_agency"], m["mine"]) for m in listed.json()] == [
        ("Hello", False, False),
        ("Of course!", True, True),
    ]


@pytest.mark.parametrize(
    ("agent_id", "plans"),
    [(AGENT_ID, QUEUED), (OTHER_AGENT_ID, QUEUED), (AGENT_ID, TAKEN)],
    ids=["queued", "queued-any-agent", "assigned"],
)
async def test_an_agent_reads_and_answers_a_queued_plan_or_their_own(agent_id, plans):
    messages = FakeMessages()
    await client_says_hello(messages)
    app = app_for(Role.AGENT, agent_id, messages, plans)

    assert (await call(app, "GET", PATH)).status_code == 200
    answered = await call(app, "POST", PATH, {"body": "On it"})
    assert answered.status_code == 201
    assert answered.json()["from_agency"] is True


@pytest.mark.parametrize(
    "plans",
    [TAKEN, [], PROPOSED, [WishPlan("quoted", AGENT_ID)]],
    ids=["taken-by-another", "no-plan", "proposed", "quoted-by-another"],
)
async def test_another_agent_gets_404(plans):
    messages = FakeMessages()
    await client_says_hello(messages)
    app = app_for(Role.AGENT, OTHER_AGENT_ID, messages, plans)

    assert (await call(app, "GET", PATH)).status_code == 404
    assert (await call(app, "POST", PATH, {"body": "hi"})).status_code == 404
    assert len(messages.stored) == 1


async def test_another_client_gets_404_on_read_and_write():
    messages = FakeMessages()
    app = app_for(Role.CLIENT, OTHER_CLIENT_ID, messages, QUEUED)

    assert (await call(app, "GET", PATH)).status_code == 404
    assert (await call(app, "POST", PATH, {"body": "hi"})).status_code == 404
    assert messages.stored == []


async def test_a_missing_wish_is_404_even_for_an_admin():
    app = app_for(Role.ADMIN, ADMIN_ID, FakeMessages())

    response = await call(app, "GET", f"/wishes/{uuid4()}/messages")

    assert response.status_code == 404


async def test_nobody_signed_in_gets_401():
    app = app_for(None, CLIENT_ID, FakeMessages())

    assert (await call(app, "GET", PATH)).status_code == 401
    assert (await call(app, "POST", PATH, {"body": "hi"})).status_code == 401


@pytest.mark.parametrize("body", ["", "   ", "x" * 2001])
async def test_an_empty_or_too_long_message_is_422(body):
    messages = FakeMessages()
    app = app_for(Role.CLIENT, CLIENT_ID, messages)

    response = await call(app, "POST", PATH, {"body": body})

    assert response.status_code == 422
    assert messages.stored == []


async def test_past_the_limit_returns_429_with_retry_after():
    messages = FakeMessages()
    app = app_for(Role.CLIENT, CLIENT_ID, messages)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(POST_LIMIT):
            assert (await client.post(PATH, json={"body": "hi"})).status_code == 201

        response = await client.post(PATH, json={"body": "hi"})

    assert response.status_code == 429
    assert response.json() == {
        "code": "too_many_requests",
        "detail": f"try again in {int(POST_WINDOW.total_seconds())} seconds",
    }
    assert response.headers["Retry-After"] == str(int(POST_WINDOW.total_seconds()))
    assert len(messages.stored) == POST_LIMIT
