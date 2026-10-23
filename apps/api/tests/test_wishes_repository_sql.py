"""The wishes repository against a real PostgreSQL: a wish reads back as it was saved.

Uses the database fixture of test_catalog_sql.py: skipped when Postgres does not answer.
"""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from novoya_api.accounts.infrastructure.db.models import UserModel
from novoya_api.shared.domain.errors import InvalidTransition
from novoya_api.wishes.domain.answers import Answers, SelectedTag
from novoya_api.wishes.domain.panel import Panel
from novoya_api.wishes.domain.wish import Destination, Wish, WishStatus
from novoya_api.wishes.infrastructure.db.models import WishModel
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from novoya_api.wishes.public import owner_id, trips
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 19, 9, 5, tzinfo=UTC)
LISBON = Destination("Portugal", "Lisbon")
PANEL = Panel.from_tags(["style:beach", "style:city", "food:seafood"])
ANSWERS = Answers(
    selected_tags=(SelectedTag("style", "beach"), SelectedTag("food", "seafood")),
    budget_max=Decimal("1500.50"),
    currency="EUR",
    persons=2,
    start_date=date(2026, 11, 2),
    end_date=date(2026, 11, 9),
)


@pytest.fixture
async def engine(database_url) -> AsyncIterator[AsyncEngine]:  # noqa: F811
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE wishes CASCADE"))  # plans reference wishes
    yield engine
    await engine.dispose()


@pytest.fixture
async def user_id(engine) -> UUID:
    async with new_session(engine) as session:
        user = UserModel(id=uuid4(), email=f"{uuid4()}@example.com", created_at=NOW)
        session.add(user)
        await session.commit()
        return user.id


def new_session(engine: AsyncEngine) -> AsyncSession:
    return async_sessionmaker(engine, expire_on_commit=False)()


async def add_wish(engine: AsyncEngine, wish: Wish) -> None:
    async with new_session(engine) as session:
        await SqlWishRepository(session).add(wish)
        await session.commit()


async def read_wish(engine: AsyncEngine, wish_id: UUID) -> Wish | None:
    async with new_session(engine) as session:
        return await SqlWishRepository(session).get(wish_id)


def shown_wish(user_id: UUID) -> Wish:
    wish = Wish.create(user_id, "A week in Lisbon", NOW)
    wish.show_panel(LISBON, PANEL, NOW)
    return wish


async def test_get_reads_back_a_wish_with_its_panel(engine, user_id):
    wish = shown_wish(user_id)
    await add_wish(engine, wish)

    assert await read_wish(engine, wish.id) == wish


async def test_get_reads_back_a_draft(engine, user_id):
    wish = Wish.create(user_id, "Somewhere warm", NOW)
    await add_wish(engine, wish)

    read = await read_wish(engine, wish.id)

    assert read == wish
    assert (read.destination, read.panel, read.answers) == (None, None, None)


async def test_get_returns_none_for_an_unknown_wish(engine):
    assert await read_wish(engine, uuid4()) is None


async def test_owner_id_returns_the_owner(engine, user_id):
    wish = shown_wish(user_id)
    await add_wish(engine, wish)

    async with new_session(engine) as session:
        assert await owner_id(wish.id, session=session) == user_id


async def test_owner_id_returns_none_for_an_unknown_wish(engine):
    async with new_session(engine) as session:
        assert await owner_id(uuid4(), session=session) is None


async def test_trips_returns_text_place_and_answers(engine, user_id):
    wish = shown_wish(user_id)
    wish.answer(ANSWERS, LATER)
    await add_wish(engine, wish)

    missing = uuid4()
    async with new_session(engine) as session:
        found = await trips([wish.id, missing], session=session)

    assert found[wish.id].text == "A week in Lisbon"
    assert found[wish.id].country == "Portugal"
    assert found[wish.id].city == "Lisbon"
    assert found[wish.id].budget_max == Decimal("1500.50")
    assert found[wish.id].persons == 2
    assert missing not in found


async def test_trips_returns_the_selected_tags_as_section_and_tag(engine, user_id):
    wish = shown_wish(user_id)
    wish.answer(ANSWERS, LATER)
    await add_wish(engine, wish)

    async with new_session(engine) as session:
        found = await trips([wish.id], session=session)

    assert found[wish.id].tags == ("style:beach", "food:seafood")


async def test_trips_of_an_unanswered_wish_has_no_tags(engine, user_id):
    wish = shown_wish(user_id)
    await add_wish(engine, wish)

    async with new_session(engine) as session:
        found = await trips([wish.id], session=session)

    assert found[wish.id].tags == ()


async def test_trips_of_a_draft_has_text_and_no_place_or_answers(engine, user_id):
    wish = Wish.create(user_id, "Somewhere warm", NOW)
    await add_wish(engine, wish)

    async with new_session(engine) as session:
        found = await trips([wish.id], session=session)

    trip = found[wish.id]
    assert trip.text == "Somewhere warm"
    assert trip.country is None
    assert trip.city is None
    assert trip.budget_max is None
    assert trip.persons is None
    assert trip.start_date is None


async def test_list_by_ids_keeps_order_and_drops_missing(engine, user_id):
    first, second = shown_wish(user_id), shown_wish(user_id)
    await add_wish(engine, first)
    await add_wish(engine, second)

    async with new_session(engine) as session:
        listed = await SqlWishRepository(session).list_by_ids([second.id, uuid4(), first.id])

    assert [wish.id for wish in listed] == [second.id, first.id]


async def test_save_stores_the_answers(engine, user_id):
    wish = shown_wish(user_id)
    await add_wish(engine, wish)

    async with new_session(engine) as session:
        wishes = SqlWishRepository(session)
        loaded = await wishes.get(wish.id)
        loaded.answer(ANSWERS, LATER)
        await wishes.save(loaded)
        await session.commit()

    read = await read_wish(engine, wish.id)
    assert read == loaded
    assert read.status is WishStatus.ANSWERED
    assert read.answers == ANSWERS
    assert read.updated_at == LATER


async def test_selected_tags_are_stored_as_section_and_tag(engine, user_id):
    wish = shown_wish(user_id)
    wish.answer(ANSWERS, LATER)
    await add_wish(engine, wish)

    async with new_session(engine) as session:
        row = await session.scalar(select(WishModel).where(WishModel.id == wish.id))

    assert row.selected_tags == [
        {"section": "style", "tag": "beach"},
        {"section": "food", "tag": "seafood"},
    ]
    assert (row.budget_max, row.currency, row.persons) == (Decimal("1500.50"), "EUR", 2)


async def test_save_after_another_request_answered_raises_invalid_transition(engine, user_id):
    wish = shown_wish(user_id)
    await add_wish(engine, wish)

    async with new_session(engine) as first, new_session(engine) as second:
        first_wishes, second_wishes = SqlWishRepository(first), SqlWishRepository(second)
        first_wish = await first_wishes.get(wish.id)
        second_wish = await second_wishes.get(wish.id)
        await second.commit()  # end the read so the first update does not wait on it

        first_wish.answer(ANSWERS, LATER)
        await first_wishes.save(first_wish)
        await first.commit()

        second_wish.answer(ANSWERS, LATER)
        with pytest.raises(InvalidTransition):
            await second_wishes.save(second_wish)
