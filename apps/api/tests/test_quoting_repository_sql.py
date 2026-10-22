"""The quotes repository against a real PostgreSQL: a quote reads back as it was added.

Uses the database fixture of test_catalog_sql.py: skipped when Postgres does not answer.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from novoya_api.accounts.infrastructure.db.models import UserModel
from novoya_api.catalog.infrastructure.db.models import OfferRow, PartnerRow
from novoya_api.planning.domain.plan import DraftItem, Plan
from novoya_api.planning.infrastructure.db.repository import SqlPlanRepository
from novoya_api.quoting.domain.errors import QuoteAlreadyAnswered
from novoya_api.quoting.domain.quote import Quote, QuoteStatus
from novoya_api.quoting.infrastructure.db.repository import SqlQuoteRepository
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.wishes.domain.wish import Wish
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Stored:
    plan_id: UUID
    client_id: UUID
    agent_id: UUID


@pytest.fixture
async def engine(database_url) -> AsyncIterator[AsyncEngine]:  # noqa: F811
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE quotes, plan_extras, plan_items, plans, wishes, offers, partners CASCADE"
            )
        )
    yield engine
    await engine.dispose()


def new_session(engine: AsyncEngine) -> AsyncSession:
    return async_sessionmaker(engine, expire_on_commit=False)()


def new_user() -> UserModel:
    return UserModel(id=uuid4(), email=f"{uuid4()}@example.com", created_at=NOW)


@pytest.fixture
async def stored(engine) -> Stored:
    client, agent = new_user(), new_user()
    partner = PartnerRow(
        id=uuid4(),
        name="Chania hotel",
        kind="hotel",
        country="Greece",
        city="Chania",
        contact_email="stay@example.com",
        contact_phone="+30 000",
        active=True,
    )
    offer = OfferRow(
        id=uuid4(),
        partner_id=partner.id,
        kind="hotel",
        title="Sea view room",
        description="Sea view room",
        country="Greece",
        city="Chania",
        min_persons=1,
        max_persons=4,
        available_from=date(2026, 4, 1),
        available_to=date(2026, 10, 31),
        tags=["style:beach"],
        featured=False,
        active=True,
    )
    async with new_session(engine) as session:
        session.add_all([client, agent, partner])
        await session.flush()
        session.add(offer)
        wish = Wish.create(client.id, "A week in Chania", NOW)
        await SqlWishRepository(session).add(wish)
        await session.flush()
        plan = Plan.propose(wish.id, True, "Sun", [DraftItem(offer.id, 1, 2, None)], 3, NOW)
        await SqlPlanRepository(session).add(plan)
        await session.commit()
    return Stored(plan.id, client.id, agent.id)


def issue(stored: Stored) -> Quote:
    quote = Quote.issue(
        stored.plan_id, stored.client_id, stored.agent_id, Decimal("1234.50"), Locale.FR, NOW
    )
    quote.pdf = b"%PDF-1.7 test"
    return quote


async def add_quote(engine: AsyncEngine, quote: Quote) -> None:
    async with new_session(engine) as session:
        await SqlQuoteRepository(session).add(quote)
        await session.commit()


async def test_get_reads_back_an_added_quote_with_its_pdf(engine, stored):
    quote = issue(stored)
    await add_quote(engine, quote)

    async with new_session(engine) as session:
        read = await SqlQuoteRepository(session).get(quote.id)

    assert read == quote


async def test_get_without_the_pdf_leaves_it_empty(engine, stored):
    quote = issue(stored)
    await add_quote(engine, quote)

    async with new_session(engine) as session:
        read = await SqlQuoteRepository(session).get(quote.id, with_pdf=False)

    assert read is not None
    assert read.pdf is None
    assert read.number == quote.number


async def test_get_with_the_pdf_after_a_read_without_it_in_one_session(engine, stored):
    quote = issue(stored)
    await add_quote(engine, quote)

    async with new_session(engine) as session:
        repository = SqlQuoteRepository(session)
        await repository.get(quote.id, with_pdf=False)
        read = await repository.get(quote.id)

    assert read is not None
    assert read.pdf == quote.pdf


async def test_get_reads_back_the_clients_answer(engine, stored):
    quote = issue(stored)
    quote.answer = QuoteStatus.ACCEPTED
    quote.decided_at = NOW + timedelta(days=1)
    await add_quote(engine, quote)

    async with new_session(engine) as session:
        read = await SqlQuoteRepository(session).get(quote.id)

    assert read == quote


async def test_save_answer_writes_the_answer_once(engine, stored):
    quote = issue(stored)
    await add_quote(engine, quote)
    quote.record_answer(QuoteStatus.ACCEPTED, "Great", NOW)

    async with new_session(engine) as session:
        await SqlQuoteRepository(session).save_answer(quote)
        await session.commit()
    async with new_session(engine) as session:
        with pytest.raises(QuoteAlreadyAnswered):
            await SqlQuoteRepository(session).save_answer(quote)
        read = await SqlQuoteRepository(session).get(quote.id)

    assert read is not None
    assert (read.answer, read.decided_at, read.client_comment) == (
        QuoteStatus.ACCEPTED,
        NOW,
        "Great",
    )


async def test_an_answer_needs_its_date(engine, stored):
    quote = issue(stored)
    quote.answer = QuoteStatus.REJECTED

    with pytest.raises(IntegrityError):
        await add_quote(engine, quote)


async def test_get_returns_none_for_an_unknown_quote(engine, stored):
    async with new_session(engine) as session:
        assert await SqlQuoteRepository(session).get(uuid4()) is None


async def test_a_plan_has_at_most_one_quote(engine, stored):
    await add_quote(engine, issue(stored))

    with pytest.raises(IntegrityError):
        await add_quote(engine, issue(stored))
