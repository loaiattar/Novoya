from dataclasses import dataclass, replace
from datetime import date
from uuid import UUID

from novoya_api.catalog.application.ports import OfferRepository, PartnerRepository
from novoya_api.catalog.application.use_cases.create_offer import blank_to_none
from novoya_api.catalog.domain import (
    ImportedRow,
    Offer,
    OfferKind,
    OfferNotFound,
    PriceUnit,
    normalize_place,
    normalize_tags,
)
from novoya_api.shared.application.unit_of_work import UnitOfWork

# The fields a PATCH may clear by sending null; any other None means "unchanged".
CLEARABLE = frozenset({"price_eur", "price_unit", "opening_months"})


@dataclass(frozen=True)
class UpdateOfferCommand:
    """None leaves a field unchanged. cleared names the fields of CLEARABLE to empty: a price
    and its unit are cleared together, or the offer is invalid."""

    offer_id: UUID
    kind: OfferKind | None = None
    title: str | None = None
    description: str | None = None
    country: str | None = None
    city: str | None = None
    min_persons: int | None = None
    max_persons: int | None = None
    available_from: date | None = None
    available_to: date | None = None
    tags: tuple[str, ...] | None = None
    featured: bool | None = None
    active: bool | None = None
    price_eur: int | None = None
    price_unit: PriceUnit | None = None
    opening_months: tuple[int, ...] | None = None
    conditions: str | None = None
    restrictions: str | None = None
    cancellation: str | None = None
    confirmation_delay_hours: int | None = None
    hidden: bool | None = None
    cleared: frozenset[str] = frozenset()


class UpdateOffer:
    """Patch an offer. An offer of an imported partner only changes featured and hidden:
    DÉTOUR owns the rest, and the next import would write it back (ADR 0014)."""

    def __init__(
        self, offers: OfferRepository, partners: PartnerRepository, uow: UnitOfWork
    ) -> None:
        self._offers = offers
        self._partners = partners
        self._uow = uow

    async def __call__(self, cmd: UpdateOfferCommand) -> Offer:
        offer = await self._offers.get(cmd.offer_id)
        if offer is None:
            raise OfferNotFound("no such offer")
        price_eur = cmd.price_eur if cmd.price_eur is not None else offer.price_eur
        price_unit = cmd.price_unit if cmd.price_unit is not None else offer.price_unit
        opening_months = (
            tuple(sorted(set(cmd.opening_months)))
            if cmd.opening_months is not None
            else offer.opening_months
        )
        if "price_eur" in cmd.cleared:
            price_eur = None
        if "price_unit" in cmd.cleared:
            price_unit = None
        if "opening_months" in cmd.cleared:
            opening_months = ()
        updated = replace(
            offer,
            kind=cmd.kind if cmd.kind is not None else offer.kind,
            title=cmd.title.strip() if cmd.title is not None else offer.title,
            description=(
                cmd.description.strip() if cmd.description is not None else offer.description
            ),
            country=normalize_place(cmd.country) if cmd.country is not None else offer.country,
            city=normalize_place(cmd.city) if cmd.city is not None else offer.city,
            min_persons=cmd.min_persons if cmd.min_persons is not None else offer.min_persons,
            max_persons=cmd.max_persons if cmd.max_persons is not None else offer.max_persons,
            available_from=(
                cmd.available_from if cmd.available_from is not None else offer.available_from
            ),
            available_to=cmd.available_to if cmd.available_to is not None else offer.available_to,
            tags=normalize_tags(cmd.tags) if cmd.tags is not None else offer.tags,
            featured=cmd.featured if cmd.featured is not None else offer.featured,
            active=cmd.active if cmd.active is not None else offer.active,
            price_eur=price_eur,
            price_unit=price_unit,
            opening_months=opening_months,
            conditions=blank_to_none(cmd.conditions)
            if cmd.conditions is not None
            else offer.conditions,
            restrictions=(
                blank_to_none(cmd.restrictions)
                if cmd.restrictions is not None
                else offer.restrictions
            ),
            cancellation=(
                blank_to_none(cmd.cancellation)
                if cmd.cancellation is not None
                else offer.cancellation
            ),
            confirmation_delay_hours=(
                cmd.confirmation_delay_hours
                if cmd.confirmation_delay_hours is not None
                else offer.confirmation_delay_hours
            ),
            hidden=cmd.hidden if cmd.hidden is not None else offer.hidden,
        )
        if replace(updated, featured=offer.featured, hidden=offer.hidden) != offer:
            partner = await self._partners.get(offer.partner_id)
            if partner is not None and partner.imported:
                raise ImportedRow(
                    "this offer comes from DÉTOUR: change it in DÉTOUR and it arrives with the "
                    "next import. Here you can only feature or hide it."
                )
        await self._offers.save(updated)
        await self._uow.commit()
        return updated
