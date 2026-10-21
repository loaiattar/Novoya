from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.catalog.public import get_extras, get_offers, search_offers
from novoya_api.planning.application.dto import ExtraSummary, OfferContact, OfferSummary


class PartnerOffers:
    """OfferCatalog read through catalog.public with the request's session. Partner names
    and contacts are dropped here: a plan never shows them."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fitting_offers(
        self,
        country: str,
        city: str | None,
        tags: Sequence[str],
        persons: int,
        start: date,
        end: date,
    ) -> list[OfferSummary]:
        offers = await search_offers(
            country, city, list(tags), persons, start, end, session=self._session
        )
        return [
            OfferSummary(
                id=offer.id,
                kind=str(offer.kind),
                title=offer.title,
                description=offer.description,
                tags=tuple(offer.tags),
                featured=offer.featured,
            )
            for offer in offers
        ]

    async def summaries_for(self, offer_ids: Sequence[UUID]) -> list[OfferSummary]:
        views = await get_offers(offer_ids, session=self._session)
        return [
            OfferSummary(
                id=offer.id,
                kind=str(offer.kind),
                title=offer.title,
                description=offer.description,
                tags=tuple(offer.tags),
                featured=offer.featured,
            )
            for offer in views
        ]

    async def contacts_for(self, offer_ids: Sequence[UUID]) -> list[OfferContact]:
        views = await get_offers(offer_ids, session=self._session)
        return [
            OfferContact(
                id=offer.id,
                kind=str(offer.kind),
                title=offer.title,
                description=offer.description,
                partner_name=offer.partner_name,
                partner_contact_email=offer.partner_contact_email,
                partner_contact_phone=offer.partner_contact_phone,
            )
            for offer in views
        ]

    async def extras_for(self, extra_ids: Sequence[UUID]) -> list[ExtraSummary]:
        extras = await get_extras(extra_ids, session=self._session)
        return [
            ExtraSummary(
                id=extra.id,
                label=extra.label,
                pricing=extra.pricing,
                unit=extra.unit,
                supplement_eur=(
                    Decimal(extra.supplement_eur) if extra.supplement_eur is not None else None
                ),
            )
            for extra in extras
        ]
