"""The admin overview (#130) with its real adapters against PostgreSQL: wishes, plans and
quotes of every client, filtered by status and searched by client or destination across the
accounts, wishes, planning and quoting modules.

Uses the fixtures of test_quoting_repository_sql.py: skipped when Postgres does not answer.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import update

from novoya_api.accounts.infrastructure.db.models import UserModel
from novoya_api.planning.domain.plan import PlanStatus
from novoya_api.planning.infrastructure.db.models import PlanModel
from novoya_api.planning.presentation.http.dependencies import (
    get_get_admin_plan,
    get_list_admin_plans,
)
from novoya_api.quoting.domain.quote import AGENCY_TIMEZONE, Quote, QuoteStatus
from novoya_api.quoting.infrastructure.db.repository import SqlQuoteRepository
from novoya_api.quoting.presentation.http.dependencies import get_list_admin_quotes
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.wishes.domain.panel import Panel
from novoya_api.wishes.domain.wish import Destination, Wish, WishStatus
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from novoya_api.wishes.presentation.http.dependencies import get_list_admin_wishes
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_quoting_repository_sql import (  # noqa: F401  (fixtures)
    NOW,
    Stored,
    engine,
    new_session,
    stored,
)


@dataclass(frozen=True)
class Agency:
    plan_id: UUID
    wish_id: UUID
    client_id: UUID
    agent_id: UUID
    other_wish_id: UUID
    quote: Quote


@pytest.fixture
async def agency(engine, stored: Stored) -> Agency:  # noqa: F811
    """Alice's plan to Chania, quoted by Paul; Bob's wish to Tokyo, not covered. The emails
    are unique: the users table is not emptied between tests."""
    bob = UserModel(
        id=uuid4(), email=f"bob.{uuid4().hex}@example.com", name="Bob Stone", created_at=NOW
    )
    async with new_session(engine) as session:
        await session.execute(
            update(UserModel)
            .where(UserModel.id == stored.client_id)
            .values(email=f"alice.{uuid4().hex}@example.com", name="Alice Martin")
        )
        await session.execute(
            update(UserModel).where(UserModel.id == stored.agent_id).values(name="Paul Agent")
        )
        plan = await session.get(PlanModel, stored.plan_id)
        wishes = SqlWishRepository(session)
        wish = await wishes.get(plan.wish_id)
        wish.show_panel(Destination("Greece", "Chania"), Panel.from_tags(["style:beach"]), NOW)
        await wishes.save(wish)
        plan.status = PlanStatus.QUOTED.value
        plan.assigned_agent_id = stored.agent_id
        plan.updated_at = NOW + timedelta(minutes=5)
        session.add(bob)
        await session.flush()
        other = Wish.create(bob.id, "Temples in Tokyo", NOW + timedelta(minutes=1))
        other.mark_not_covered(Destination("Japan", "Tokyo"), NOW + timedelta(minutes=1))
        await wishes.add(other)
        # Sent now, so it is still valid whatever day the tests run.
        quote = Quote.issue(
            stored.plan_id,
            stored.client_id,
            stored.agent_id,
            Decimal("1234.50"),
            Locale.FR,
            datetime.now(UTC),
        )
        quote.pdf = b"%PDF-1.7 test"
        await SqlQuoteRepository(session).add(quote)
        await session.commit()
    return Agency(stored.plan_id, wish.id, stored.client_id, stored.agent_id, other.id, quote)


async def test_every_wish_is_listed_last_changed_first_with_its_client(engine, agency):  # noqa: F811
    async with new_session(engine) as session:
        wishes = await get_list_admin_wishes(session)()

    # Bob's wish changed a minute after Alice's answer.
    assert [wish.id for wish in wishes] == [agency.other_wish_id, agency.wish_id]
    alice = wishes[1]
    assert (alice.status, alice.city, alice.country) == ("panel_shown", "Chania", "Greece")
    assert alice.client.name == "Alice Martin"
    assert alice.client.email.startswith("alice.")


@pytest.mark.parametrize("query", ["tokyo", "JAPAN", "bob", "Stone"])
async def test_wishes_are_searched_by_client_or_destination(engine, agency, query):  # noqa: F811
    async with new_session(engine) as session:
        wishes = await get_list_admin_wishes(session)(query=query)

    assert [wish.id for wish in wishes] == [agency.other_wish_id]


async def test_wishes_are_filtered_by_status(engine, agency):  # noqa: F811
    async with new_session(engine) as session:
        wishes = await get_list_admin_wishes(session)(WishStatus.NOT_COVERED)

    assert [wish.text for wish in wishes] == ["Temples in Tokyo"]


async def test_every_plan_is_listed_with_its_client_and_agent(engine, agency):  # noqa: F811
    async with new_session(engine) as session:
        [entry] = await get_list_admin_plans(session)()

    assert (entry.id, entry.status, entry.city) == (agency.plan_id, "quoted", "Chania")
    assert entry.client.email.startswith("alice.")
    assert entry.agent.name == "Paul Agent"


@pytest.mark.parametrize("query", ["chania", "alice", "Martin"])
async def test_plans_are_searched_by_client_or_destination(engine, agency, query):  # noqa: F811
    async with new_session(engine) as session:
        entries = await get_list_admin_plans(session)(query=query)

    assert [entry.id for entry in entries] == [agency.plan_id]


async def test_a_plan_search_without_a_match_is_empty(engine, agency):  # noqa: F811
    async with new_session(engine) as session:
        assert await get_list_admin_plans(session)(query="tokyo") == []


async def test_plans_are_filtered_by_status_and_wish(engine, agency):  # noqa: F811
    async with new_session(engine) as session:
        use_case = get_list_admin_plans(session)
        assert await use_case(PlanStatus.REQUESTED) == []
        assert len(await use_case(PlanStatus.QUOTED, wish_id=agency.wish_id)) == 1
        assert await use_case(wish_id=agency.other_wish_id) == []


async def test_the_admin_reads_any_plan_with_its_prices_and_people(engine, agency):  # noqa: F811
    async with new_session(engine) as session:
        view = await get_get_admin_plan(session)(agency.plan_id)

    assert view.plan.id == agency.plan_id
    assert [item.title for item in view.plan.items] == ["Sea view room"]
    assert view.plan.items[0].partner_name == "Chania hotel"
    assert view.client.name == "Alice Martin"
    assert view.agent.name == "Paul Agent"


async def test_every_quote_is_listed_with_its_trip_client_and_status(engine, agency):  # noqa: F811
    async with new_session(engine) as session:
        [quote] = await get_list_admin_quotes(session)()

    assert (quote.id, quote.number) == (agency.quote.id, agency.quote.number)
    assert quote.status == QuoteStatus.OPEN
    assert quote.total == Decimal("1234.50")
    assert quote.trip.city == "Chania"
    assert quote.client.email.startswith("alice.")


@pytest.mark.parametrize("query", ["chania", "alice."])
async def test_quotes_are_searched_by_client_or_destination(engine, agency, query):  # noqa: F811
    async with new_session(engine) as session:
        quotes = await get_list_admin_quotes(session)(query=query)

    assert [quote.id for quote in quotes] == [agency.quote.id]


async def test_quotes_are_filtered_by_status_and_plan(engine, agency):  # noqa: F811
    async with new_session(engine) as session:
        use_case = get_list_admin_quotes(session)
        assert len(await use_case(QuoteStatus.OPEN)) == 1
        assert await use_case(QuoteStatus.EXPIRED) == []
        assert await use_case(QuoteStatus.ACCEPTED) == []
        assert len(await use_case(plan_id=agency.plan_id)) == 1
        assert await use_case(plan_id=uuid4()) == []


async def test_a_quote_past_its_validity_is_expired(engine, agency):  # noqa: F811
    async with new_session(engine) as session:
        await SqlQuoteRepository(session).delete_for_client(agency.client_id)
        sent = datetime.now(UTC) - timedelta(days=8)  # a week to answer, and a day more
        old = Quote.issue(
            agency.plan_id, agency.client_id, agency.agent_id, Decimal("99.00"), Locale.EN, sent
        )
        old.pdf = b"%PDF-1.7 old"
        await SqlQuoteRepository(session).add(old)
        await session.commit()

    async with new_session(engine) as session:
        [quote] = await get_list_admin_quotes(session)(QuoteStatus.EXPIRED)

    assert (quote.id, quote.status) == (old.id, QuoteStatus.EXPIRED)


async def test_the_clients_answer_is_the_quotes_status(engine, agency):  # noqa: F811
    async with new_session(engine) as session:
        quotes = SqlQuoteRepository(session)
        quote = await quotes.get(agency.quote.id, with_pdf=False)
        quote.record_answer(QuoteStatus.REJECTED, None, datetime.now(UTC))
        await quotes.save_answer(quote)
        await session.commit()

    async with new_session(engine) as session:
        use_case = get_list_admin_quotes(session)
        [rejected] = await use_case(QuoteStatus.REJECTED)
        assert (rejected.id, rejected.status) == (agency.quote.id, QuoteStatus.REJECTED)
        assert await use_case(QuoteStatus.OPEN) == []
        assert await use_case(QuoteStatus.ACCEPTED) == []


async def test_the_whole_last_day_counts_in_paris(engine, agency):  # noqa: F811
    # Valid until 18:00 on 29 October in Paris: open all that day, expired the next.
    evening = datetime(2026, 10, 29, 20, tzinfo=AGENCY_TIMEZONE)
    async with new_session(engine) as session:
        quotes = SqlQuoteRepository(session)
        await quotes.delete_for_client(agency.client_id)
        sent = evening - timedelta(days=7, hours=2)
        late = Quote.issue(
            agency.plan_id, agency.client_id, agency.agent_id, Decimal("99.00"), Locale.EN, sent
        )
        late.pdf = b"%PDF-1.7 late"
        await quotes.add(late)
        await session.commit()

    async with new_session(engine) as session:
        quotes = SqlQuoteRepository(session)
        assert [q.id for q in await quotes.search(None, QuoteStatus.OPEN, evening)] == [late.id]
        assert await quotes.search(None, QuoteStatus.EXPIRED, evening) == []
        next_day = evening + timedelta(hours=5)
        assert await quotes.search(None, QuoteStatus.OPEN, next_day) == []
        assert [q.id for q in await quotes.search(None, QuoteStatus.EXPIRED, next_day)] == [late.id]
