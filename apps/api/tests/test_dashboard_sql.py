"""The dashboard's counts on PostgreSQL: each module counts its own rows."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import update

from novoya_api.catalog.infrastructure.db.models import ExtraRow, PartnerRow
from novoya_api.dashboard.presentation.http.dependencies import get_get_admin_stats
from novoya_api.quoting.domain.quote import QuoteStatus
from novoya_api.quoting.infrastructure.db.repository import SqlQuoteRepository
from tests.test_admin_overview_sql import Agency, agency  # noqa: F401  (fixture)
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_quoting_repository_sql import engine, new_session, stored  # noqa: F401


def an_extra(**values) -> ExtraRow:
    return ExtraRow(
        id=uuid4(),
        category="Comfort",
        label="Quiet room",
        description="",
        pricing="included",
        unit="",
        **values,
    )


async def test_the_catalog_plans_and_quotes_are_counted(engine, agency: Agency):  # noqa: F811
    async with new_session(engine) as session:
        stats = await get_get_admin_stats(session)()

    # The partners, offers, plans and quotes tables start empty; agency adds one of each.
    catalog = stats.catalog
    assert (catalog.partners.active, catalog.partners.hidden, catalog.partners.inactive) == (
        1,
        0,
        0,
    )
    assert catalog.offers.active == 1
    assert stats.plans == {
        "proposed": 0,
        "requested": 0,
        "negotiating": 0,
        "quoted": 1,
        "accepted": 0,
        "rejected": 0,
    }
    assert stats.quotes == {"open": 1, "expired": 0, "accepted": 0, "rejected": 0}
    assert set(stats.users) == {"client", "agent", "admin", "super_admin"}


async def test_a_hidden_partner_and_extras_by_state(engine, agency: Agency):  # noqa: F811
    async with new_session(engine) as session:
        before = (await get_get_admin_stats(session)()).catalog.extras
        await session.execute(update(PartnerRow).values(hidden=True))
        session.add_all([an_extra(hidden=True), an_extra(active=False), an_extra()])
        await session.commit()

    async with new_session(engine) as session:
        catalog = (await get_get_admin_stats(session)()).catalog

    assert (catalog.partners.active, catalog.partners.hidden) == (0, 1)
    # Its offer is still switched on, but clients no longer see it: it counts as hidden.
    assert (catalog.offers.active, catalog.offers.hidden, catalog.offers.inactive) == (0, 1, 0)
    extras = catalog.extras
    assert (extras.active, extras.hidden, extras.inactive) == (
        before.active + 1,
        before.hidden + 1,
        before.inactive + 1,
    )


async def test_an_offer_under_an_inactive_partner_is_inactive(engine, agency: Agency):  # noqa: F811
    async with new_session(engine) as session:
        await session.execute(update(PartnerRow).values(active=False))
        await session.commit()

    async with new_session(engine) as session:
        offers = (await get_get_admin_stats(session)()).catalog.offers

    assert (offers.active, offers.hidden, offers.inactive) == (0, 0, 1)


async def test_an_answer_and_an_expiry_move_the_quote_counts(engine, agency: Agency):  # noqa: F811
    async with new_session(engine) as session:
        quotes = SqlQuoteRepository(session)
        assert (await quotes.count_by_status(datetime.now(UTC)))[QuoteStatus.OPEN] == 1
        # The day after the validity day, in Paris, the quote has expired.
        later = agency.quote.valid_until + timedelta(days=1)
        counts = await quotes.count_by_status(later)
        assert (counts[QuoteStatus.OPEN], counts[QuoteStatus.EXPIRED]) == (0, 1)

        quote = await quotes.get(agency.quote.id, with_pdf=False)
        quote.record_answer(QuoteStatus.ACCEPTED, None, datetime.now(UTC))
        await quotes.save_answer(quote)
        await session.commit()

    async with new_session(engine) as session:
        stats = await get_get_admin_stats(session)()

    assert stats.quotes == {"open": 0, "expired": 0, "accepted": 1, "rejected": 0}
