from sqlalchemy import ColumnElement, FromClause, and_, func, join, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.catalog.application.dto import CatalogCounts, RowCounts
from novoya_api.catalog.infrastructure.db.models import ExtraRow, OfferRow, PartnerRow, ReviewRow


async def count_catalog(session: AsyncSession) -> CatalogCounts:
    """One query per table: only counts are read."""
    partners = await _rows(session, PartnerRow.__table__, PartnerRow.active, PartnerRow.hidden)
    # An offer is listed only when its partner is too, as in the client search: an offer
    # under a hidden partner counts as hidden, one under an inactive partner as inactive.
    offers = await _rows(
        session,
        join(OfferRow, PartnerRow, OfferRow.partner_id == PartnerRow.id),
        and_(OfferRow.active, PartnerRow.active),
        or_(OfferRow.hidden, PartnerRow.hidden),
    )
    extras = await _rows(session, ExtraRow.__table__, ExtraRow.active, ExtraRow.hidden)
    hidden, published = (
        await session.execute(
            select(
                func.count().filter(ReviewRow.hidden),
                func.count().filter(not_(ReviewRow.hidden)),
            )
        )
    ).one()
    return CatalogCounts(partners, offers, extras, published, hidden)


async def _rows(
    session: AsyncSession,
    rows: FromClause,
    active: ColumnElement[bool],
    hidden: ColumnElement[bool],
) -> RowCounts:
    """Hidden wins over inactive: a hidden row is counted once, as hidden."""
    counts = select(
        func.count().filter(and_(active, not_(hidden))),
        func.count().filter(hidden),
        func.count().filter(and_(not_(active), not_(hidden))),
    ).select_from(rows)
    active_count, hidden_count, inactive_count = (await session.execute(counts)).one()
    return RowCounts(active_count, hidden_count, inactive_count)
