from dataclasses import dataclass
from uuid import UUID

from novoya_api.catalog.domain import Extra, Offer, OfferKind, Partner


@dataclass(frozen=True, slots=True)
class OfferView:
    """A listed offer, as other modules see it. No price: an agent negotiates that per trip
    (the indicative price is only for the offer page, ADR 0014).

    It carries the partner's name and contact; other modules decide who may see them."""

    id: UUID
    kind: OfferKind
    title: str
    description: str
    country: str
    city: str
    min_persons: int
    max_persons: int
    tags: tuple[str, ...]
    featured: bool
    partner_name: str
    partner_contact_email: str
    partner_contact_phone: str | None

    @classmethod
    def of(cls, offer: Offer, partner: Partner) -> "OfferView":
        return cls(
            id=offer.id,
            kind=offer.kind,
            title=offer.title,
            description=offer.description,
            country=offer.country,
            city=offer.city,
            min_persons=offer.min_persons,
            max_persons=offer.max_persons,
            tags=offer.tags,
            featured=offer.featured,
            partner_name=partner.name,
            partner_contact_email=partner.contact_email,
            partner_contact_phone=partner.contact_phone,
        )


@dataclass(frozen=True, slots=True)
class ExtraView:
    """An active extra, as other modules see it. supplement_eur only for a supplement."""

    id: UUID
    label: str
    pricing: str
    supplement_eur: int | None
    unit: str

    @classmethod
    def of(cls, extra: Extra) -> "ExtraView":
        return cls(
            id=extra.id,
            label=extra.label,
            pricing=extra.pricing.value,
            supplement_eur=extra.supplement_eur,
            unit=extra.unit,
        )


@dataclass(frozen=True)
class RowCounts:
    """How many rows clients may see, how many an admin hid, and how many left the DÉTOUR
    export (inactive, not hidden). An offer counts with its partner: it is hidden when
    either is hidden, inactive when either is inactive."""

    active: int
    hidden: int
    inactive: int


@dataclass(frozen=True)
class CatalogCounts:
    """The catalog in numbers, for the admin dashboard. A review is published or hidden."""

    partners: RowCounts
    offers: RowCounts
    extras: RowCounts
    reviews_published: int
    reviews_hidden: int
