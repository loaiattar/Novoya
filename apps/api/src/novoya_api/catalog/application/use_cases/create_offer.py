from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from novoya_api.catalog.application.ports import OfferRepository, PartnerRepository
from novoya_api.catalog.domain import (
    ImportedRow,
    Offer,
    OfferKind,
    PartnerNotFound,
    PriceUnit,
    normalize_place,
    normalize_tags,
)
from novoya_api.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class CreateOfferCommand:
    partner_id: UUID
    kind: OfferKind
    title: str
    description: str
    country: str
    city: str
    min_persons: int
    max_persons: int
    available_from: date
    available_to: date
    tags: tuple[str, ...]
    featured: bool = False
    active: bool = True
    price_eur: int | None = None
    price_unit: PriceUnit | None = None
    opening_months: tuple[int, ...] = ()
    conditions: str | None = None
    restrictions: str | None = None
    cancellation: str | None = None
    confirmation_delay_hours: int | None = None


class CreateOffer:
    """Add an offer to a hand-made partner. An imported partner's offers come from DÉTOUR:
    one added here would be deactivated by the next import, so it is refused."""

    def __init__(
        self, offers: OfferRepository, partners: PartnerRepository, uow: UnitOfWork
    ) -> None:
        self._offers = offers
        self._partners = partners
        self._uow = uow

    async def __call__(self, cmd: CreateOfferCommand) -> Offer:
        partner = await self._partners.get(cmd.partner_id)
        if partner is None:
            raise PartnerNotFound("no such partner")
        if partner.imported:
            raise ImportedRow(
                "this partner comes from DÉTOUR: add its offers in DÉTOUR, they arrive with the "
                "next import."
            )
        offer = Offer(
            id=uuid4(),
            partner_id=cmd.partner_id,
            kind=cmd.kind,
            title=cmd.title.strip(),
            description=cmd.description.strip(),
            country=normalize_place(cmd.country),
            city=normalize_place(cmd.city),
            min_persons=cmd.min_persons,
            max_persons=cmd.max_persons,
            available_from=cmd.available_from,
            available_to=cmd.available_to,
            tags=normalize_tags(cmd.tags),
            featured=cmd.featured,
            active=cmd.active,
            price_eur=cmd.price_eur,
            price_unit=cmd.price_unit,
            opening_months=tuple(sorted(set(cmd.opening_months))),
            conditions=blank_to_none(cmd.conditions),
            restrictions=blank_to_none(cmd.restrictions),
            cancellation=blank_to_none(cmd.cancellation),
            confirmation_delay_hours=cmd.confirmation_delay_hours,
        )
        await self._offers.add(offer)
        await self._uow.commit()
        return offer


def blank_to_none(value: str | None) -> str | None:
    """Stripped, and None when blank."""
    if value is None:
        return None
    return value.strip() or None
