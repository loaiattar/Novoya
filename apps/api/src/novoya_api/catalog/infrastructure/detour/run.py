"""Writes the DÉTOUR catalog in one transaction: all of it or nothing.

Partners, offers and extras are inserted or updated by their stable id. Reviews are replaced:
a review that left avis_diffusables (consent withdrawn) is deleted here too. A partner, offer
or extra that left the export is kept, since plans may point to it, but made inactive; it is
active again if it comes back.

DÉTOUR owns imported rows (ADR 0014): every column it exports, `active` included, is written
again on each import, and the admin API refuses to change them (409 imported_row), so a fix
is made in DÉTOUR. Novoya owns two columns the import never writes: `hidden` (the agent's
switch on a partner, an offer or an extra, kept across imports) and `featured` (offers). A
hidden row is left out everywhere an inactive one is.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.catalog.domain import Extra, Offer, Partner, Review
from novoya_api.catalog.infrastructure.db.models import ExtraRow, OfferRow, PartnerRow, ReviewRow
from novoya_api.catalog.infrastructure.detour.mapping import SOURCE, DetourCatalog
from novoya_api.catalog.infrastructure.detour.read import read_catalog
from novoya_api.shared.infrastructure.db.session import get_sessionmaker

# Under PostgreSQL's 32767 parameters per statement for the widest table (offers).
BATCH = 500


@dataclass(frozen=True)
class ImportCounts:
    partners: int
    offers: int
    reviews: int
    extras: int


async def import_detour(path: Path) -> ImportCounts:
    """Reads the whole export first (DetourImportError before any write), then writes it."""
    catalog = read_catalog(path)
    async with get_sessionmaker()() as session:
        await _upsert(session, PartnerRow, [_partner(item) for item in catalog.partners])
        await _upsert(
            session, OfferRow, [_offer(item) for item in catalog.offers], keep={"featured"}
        )
        await _upsert(session, ExtraRow, [_extra(item) for item in catalog.extras])
        await _deactivate_missing(session, catalog)
        await session.execute(
            delete(ReviewRow).where(ReviewRow.id.not_in([item.id for item in catalog.reviews]))
        )
        await _upsert(session, ReviewRow, [_review(item) for item in catalog.reviews])
        await session.commit()
    return ImportCounts(
        partners=len(catalog.partners),
        offers=len(catalog.offers),
        reviews=len(catalog.reviews),
        extras=len(catalog.extras),
    )


async def _deactivate_missing(session: AsyncSession, catalog: DetourCatalog) -> None:
    """Rows of an earlier import that this export no longer has. Hand-added partners and
    their offers are not touched; every extra comes from DÉTOUR."""
    imported = select(PartnerRow.id).where(PartnerRow.source == SOURCE)
    await session.execute(
        update(PartnerRow)
        .where(
            PartnerRow.source == SOURCE,
            PartnerRow.id.not_in([item.id for item in catalog.partners]),
        )
        .values(active=False)
    )
    await session.execute(
        update(OfferRow)
        .where(
            OfferRow.partner_id.in_(imported),
            OfferRow.id.not_in([item.id for item in catalog.offers]),
        )
        .values(active=False)
    )
    await session.execute(
        update(ExtraRow)
        .where(ExtraRow.id.not_in([item.id for item in catalog.extras]))
        .values(active=False)
    )


async def _upsert(
    session: AsyncSession,
    model: type,
    rows: Sequence[dict],
    keep: frozenset[str] | set[str] = frozenset(),
) -> None:
    """Insert, or update every column given but the id and `keep`. `hidden` is never given:
    agents decide it in Novoya, like `featured`, which an offer's insert sets to false."""
    for start in range(0, len(rows), BATCH):
        batch = rows[start : start + BATCH]
        stmt = insert(model).values(batch)
        updates = {key: stmt.excluded[key] for key in batch[0] if key != "id" and key not in keep}
        await session.execute(stmt.on_conflict_do_update(index_elements=["id"], set_=updates))


def _partner(partner: Partner) -> dict:
    return {
        "id": partner.id,
        "name": partner.name,
        "kind": partner.kind.value,
        "country": partner.country,
        "city": partner.city,
        "contact_email": partner.contact_email,
        "contact_phone": partner.contact_phone,
        "active": partner.active,
        "source": SOURCE,
    }


def _offer(offer: Offer) -> dict:
    return {
        "id": offer.id,
        "partner_id": offer.partner_id,
        "kind": offer.kind.value,
        "title": offer.title,
        "description": offer.description,
        "country": offer.country,
        "city": offer.city,
        "min_persons": offer.min_persons,
        "max_persons": offer.max_persons,
        "available_from": offer.available_from,
        "available_to": offer.available_to,
        "tags": list(offer.tags),
        "featured": offer.featured,
        "active": offer.active,
        "price_eur": offer.price_eur,
        "price_unit": offer.price_unit.value if offer.price_unit is not None else None,
        "opening_months": list(offer.opening_months),
        "conditions": offer.conditions,
        "restrictions": offer.restrictions,
        "cancellation": offer.cancellation,
        "confirmation_delay_hours": offer.confirmation_delay_hours,
    }


def _review(review: Review) -> dict:
    return {
        "id": review.id,
        "country": review.country,
        "city": review.city,
        "rating": review.rating,
        "reviewed_on": review.reviewed_on,
        "text": review.text,
        "author": review.author,
    }


def _extra(extra: Extra) -> dict:
    return {
        "id": extra.id,
        "category": extra.category,
        "label": extra.label,
        "description": extra.description,
        "pricing": extra.pricing.value,
        "supplement_eur": extra.supplement_eur,
        "unit": extra.unit,
        "constraints": list(extra.constraints),
        "active": extra.active,
    }
