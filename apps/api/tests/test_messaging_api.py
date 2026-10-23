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
from novoya_api.messaging.application.use_cases.post_message import PostMessage
from novoya_api.messaging.domain.message import Message
from novoya_api.messaging.presentation.http.dependencies import (
    get_list_messages,
    get_post_message,
)
from novoya_api.shared.domain.value_objects import Locale

NOW = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)
WISH_ID = UUID("00000000-0000-0000-0000-00000000a001")
CLIENT_ID = UUID("00000000-0000-0000-0000-0000000000c1")
OTHER_CLIENT_ID = UUID("00000000-0000-0000-0000-0000000000c2")
AGENT_ID = UUID("00000000-0000-0000-0000-0000000000a9")


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


class FakeUow:
    commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


class FixedClock:
    def now(self) -> datetime:
        return NOW


def app_for(role: Role | None, user_id: UUID, messages: FakeMessages):
    app = create_app()
    app.dependency_overrides[get_list_messages] = lambda: ListMessages(messages, FakeWishes())
    app.dependency_overrides[get_post_message] = lambda: PostMessage(
        messages, FakeWishes(), FakeUow(), FixedClock()
    )
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
    assert listed.status_code == 200
    assert [m["body"] for m in listed.json()] == ["Can we add a day in Kyoto?"]
    assert listed.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("role", [Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN])
async def test_staff_read_and_answer_any_conversation(role):
    messages = FakeMessages()
    await PostMessage(messages, FakeWishes(), FakeUow(), FixedClock())(
        WISH_ID, CLIENT_ID, staff=False, body="Hello"
    )
    app = app_for(role, AGENT_ID, messages)

    answered = await call(app, "POST", PATH, {"body": "Of course!"})
    listed = await call(app, "GET", PATH)

    assert answered.status_code == 201
    assert answered.json()["from_agency"] is True
    body = listed.json()
    assert [(m["body"], m["from_agency"], m["mine"]) for m in body] == [
        ("Hello", False, False),
        ("Of course!", True, True),
    ]


async def test_another_client_gets_404_on_read_and_write():
    messages = FakeMessages()
    app = app_for(Role.CLIENT, OTHER_CLIENT_ID, messages)

    assert (await call(app, "GET", PATH)).status_code == 404
    assert (await call(app, "POST", PATH, {"body": "hi"})).status_code == 404
    assert messages.stored == []


async def test_a_missing_wish_is_404_even_for_staff():
    app = app_for(Role.AGENT, AGENT_ID, FakeMessages())

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
