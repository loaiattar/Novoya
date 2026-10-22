"""What other modules may use from catalog. Nothing else in catalog may be imported.

- covered_destinations() -> destinations with at least one listed offer (listed: an active,
  not hidden offer of an active, not hidden partner)
- tags_at(country, city) -> tags of listed offers there (city None = the whole country)
- search_offers(country, city, tags, persons, start, end) -> listed offers that fit, as
  OfferView. OfferView carries partner name and contact; other modules decide who may see them.
- get_offers(ids) -> OfferView for those ids, including inactive (a saved plan still
  needs titles). Callers drop partner fields when the client must not see them.
- get_extras(ids) -> ExtraView for the listed extras (active, not hidden) among those ids,
  in that order (label, pricing included/supplement/on_quote, supplement_eur). Others are
  omitted.
- canonical_country(name) -> the English name Novoya stores for a country written in French
  or English ("Grèce", "greece" -> "Greece"), or None. No database.
- OfferKind: hotel, guide, transport, activity, agency (for OpenAPI on the plan).
- count_catalog() -> CatalogCounts: partners, offers and extras (active, hidden, inactive)
  and reviews (published, hidden), for the admin dashboard. Counts only.

Country and city matching is case-insensitive. Prefer the names returned by
covered_destinations() (English country names) so the LLM and the panel stay consistent.

Inside a request, pass the request's session: each call then reads through it instead of
taking a second connection from the pool.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.catalog.application.dto import CatalogCounts, ExtraView, OfferView
from novoya_api.catalog.application.dto import RowCounts as RowCounts
from novoya_api.catalog.application.use_cases.get_extras import GetExtras
from novoya_api.catalog.application.use_cases.get_offers import GetOffers
from novoya_api.catalog.application.use_cases.list_destinations import ListDestinations
from novoya_api.catalog.application.use_cases.list_tags_at import ListTagsAt
from novoya_api.catalog.application.use_cases.search_offers import SearchOffers
from novoya_api.catalog.domain.kinds import OfferKind as OfferKind
from novoya_api.catalog.infrastructure import countries
from novoya_api.catalog.infrastructure.db.counts import count_catalog as _count_catalog
from novoya_api.catalog.infrastructure.db.repositories import (
    SqlExtraRepository,
    SqlOfferRepository,
)
from novoya_api.shared.infrastructure.db.session import get_sessionmaker


async def covered_destinations(*, session: AsyncSession | None = None) -> list[tuple[str, str]]:
    """Destinations with at least one listed offer. Countries are in English."""
    async with _reading(session) as reading:
        return await ListDestinations(SqlOfferRepository(reading))()


async def tags_at(
    country: str, city: str | None, *, session: AsyncSession | None = None
) -> list[str]:
    """Tags of listed offers at this destination, as section:tag. city None = the whole country."""
    async with _reading(session) as reading:
        return await ListTagsAt(SqlOfferRepository(reading))(country, city)


async def search_offers(
    country: str,
    city: str | None,
    tags: list[str],
    persons: int,
    start: date,
    end: date,
    *,
    session: AsyncSession | None = None,
) -> list[OfferView]:
    """Listed offers at this destination that fit the group and the whole trip, best first.

    With tags, an offer needs at least one of them (section:tag); without, all fitting offers
    come back. city None = the whole country."""
    async with _reading(session) as reading:
        return await SearchOffers(SqlOfferRepository(reading))(
            country, city, tags, persons, start, end
        )


async def get_offers(
    ids: Sequence[UUID], *, session: AsyncSession | None = None
) -> list[OfferView]:
    """Offers by id, in that order, including inactive. Missing ids are omitted."""
    async with _reading(session) as reading:
        return await GetOffers(SqlOfferRepository(reading))(ids)


async def get_extras(
    ids: Sequence[UUID], *, session: AsyncSession | None = None
) -> list[ExtraView]:
    """Listed extras by id, in that order. Inactive, hidden and unknown ids are omitted."""
    async with _reading(session) as reading:
        return await GetExtras(SqlExtraRepository(reading))(ids)


async def count_catalog(*, session: AsyncSession) -> CatalogCounts:
    """How many partners, offers, extras and reviews, by state. For admins only: the
    caller's router must require the admin role."""
    return await _count_catalog(session)


def canonical_country(name: str) -> str | None:
    """The English country name for a name in French or English, any case; else None."""
    return countries.canonical_country(name)


@asynccontextmanager
async def _reading(session: AsyncSession | None) -> AsyncIterator[AsyncSession]:
    """The caller's session, or a session of our own that is closed afterwards."""
    if session is not None:
        yield session
        return
    async with get_sessionmaker()() as own:
        yield own
