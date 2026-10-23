"""The messages repository against a real PostgreSQL: a conversation reads back oldest
first, the cap keeps the newest, and erasing the wish erases its messages.

Uses the database fixture of test_catalog_sql.py: skipped when Postgres does not answer.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from novoya_api.accounts.infrastructure.db.models import UserModel
from novoya_api.messaging.domain.message import Message
from novoya_api.messaging.infrastructure.db import repository as message_repository
from novoya_api.messaging.infrastructure.db.models import MessageModel
from novoya_api.messaging.infrastructure.db.repository import SqlMessageRepository
from novoya_api.wishes.domain.wish import Wish
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)

NOW = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)


@pytest.fixture
async def engine(database_url) -> AsyncIterator[AsyncEngine]:  # noqa: F811
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE messages, plan_extras, plan_items, plans, wishes CASCADE")
        )
    yield engine
    await engine.dispose()


def new_session(engine: AsyncEngine) -> AsyncSession:
    return async_sessionmaker(engine, expire_on_commit=False)()


@pytest.fixture
async def wish(engine) -> tuple[UUID, UUID]:
    """(user id, wish id)"""
    async with new_session(engine) as session:
        user = UserModel(id=uuid4(), email=f"{uuid4()}@example.com", created_at=NOW)
        session.add(user)
        await session.flush()
        wish = Wish.create(user.id, "Two weeks in Japan", NOW)
        await SqlWishRepository(session).add(wish)
        await session.commit()
        return user.id, wish.id


async def write(engine: AsyncEngine, wish_id: UUID, author_id: UUID, bodies: list[str]) -> None:
    async with new_session(engine) as session:
        repository = SqlMessageRepository(session)
        for minutes, body in enumerate(bodies):
            at = NOW + timedelta(minutes=minutes)
            await repository.add(Message.write(wish_id, author_id, False, body, at))
        await session.commit()


async def test_a_conversation_reads_back_oldest_first(engine, wish):
    user_id, wish_id = wish
    await write(engine, wish_id, user_id, ["first", "second", "third"])

    async with new_session(engine) as session:
        found = await SqlMessageRepository(session).list_for_wish(wish_id)

    assert [m.body for m in found] == ["first", "second", "third"]
    assert found[0].author_id == user_id
    assert found[0].wish_id == wish_id
    assert found[0].from_agency is False
    assert found[0].sent_at == NOW


async def test_the_cap_keeps_the_newest_messages(engine, wish, monkeypatch):
    user_id, wish_id = wish
    await write(engine, wish_id, user_id, ["1", "2", "3", "4", "5"])
    monkeypatch.setattr(message_repository, "CONVERSATION_CAP", 3)

    async with new_session(engine) as session:
        found = await SqlMessageRepository(session).list_for_wish(wish_id)

    assert [m.body for m in found] == ["3", "4", "5"]


async def test_erasing_the_wishes_erases_their_messages(engine, wish):
    user_id, wish_id = wish
    await write(engine, wish_id, user_id, ["hello"])

    async with new_session(engine) as session:
        await SqlWishRepository(session).delete_for_user(user_id)
        await session.commit()

    async with new_session(engine) as session:
        left = await session.scalar(select(func.count()).select_from(MessageModel))
    assert left == 0
