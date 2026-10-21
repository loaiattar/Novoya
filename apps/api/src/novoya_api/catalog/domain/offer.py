import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID

from novoya_api.catalog.domain.kinds import OfferKind
from novoya_api.catalog.domain.partner import Partner
from novoya_api.shared.domain.errors import InvalidInput


class InvalidOffer(InvalidInput):
    """Person limits, dates or tags are inconsistent."""

    code = "invalid_offer"


class PriceUnit(StrEnum):
    """What the indicative price is for: always one person."""

    PERSON_NIGHT = "person/night"
    PERSON_TRIP = "person/trip"
    PERSON_ACTIVITY = "person/activity"


@dataclass(frozen=True)
class Offer:
    """A partner product. Its price, when the partner gave one, is indicative only (ADR 0014):
    the agent still negotiates the price of each trip, and the quote has that one.

    active comes from the partner (the DÉTOUR export for imported offers); hidden is the
    agent's switch in Novoya, which the import never changes. A hidden offer is unused, like
    an inactive one."""

    id: UUID
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
    featured: bool
    active: bool
    price_eur: int | None = None
    price_unit: PriceUnit | None = None
    opening_months: tuple[int, ...] = ()  # 1-12; empty means no month is given
    conditions: str | None = None
    restrictions: str | None = None
    cancellation: str | None = None
    confirmation_delay_hours: int | None = None
    hidden: bool = False

    def __post_init__(self) -> None:
        if self.min_persons < 1 or self.max_persons < self.min_persons:
            raise InvalidOffer("person limits must be at least 1 and min <= max")
        if self.available_from > self.available_to:
            raise InvalidOffer("available_from must be on or before available_to")
        for tag in self.tags:
            if not _is_catalog_tag(tag):
                raise InvalidOffer("tags must be section:tag")
        if (self.price_eur is None) != (self.price_unit is None):
            raise InvalidOffer("a price needs its unit, and a unit its price")
        if self.price_eur is not None and self.price_eur <= 0:
            raise InvalidOffer("the price must be more than 0")
        if any(not 1 <= month <= 12 for month in self.opening_months):
            raise InvalidOffer("opening months go from 1 to 12")
        if self.confirmation_delay_hours is not None and self.confirmation_delay_hours < 0:
            raise InvalidOffer("the confirmation delay cannot be negative")

    def is_listed_with(self, partner: Partner) -> bool:
        """Inactive or hidden partners hide their offers; inactive or hidden offers are unused."""
        if partner.id != self.partner_id:
            raise InvalidOffer("offer does not belong to this partner")
        return partner.lists_offers() and self.active and not self.hidden

    def fits(self, persons: int, start: date, end: date) -> bool:
        """True when the group size and trip dates sit inside the offer's limits, and every
        month of the trip is an opening month (when the offer gives any)."""
        if start > end:
            return False
        if persons < self.min_persons or persons > self.max_persons:
            return False
        if start < self.available_from or end > self.available_to:
            return False
        return self._open_during(start, end)

    def _open_during(self, start: date, end: date) -> bool:
        """Every month the trip touches is an opening month. No months given: always open."""
        if not self.opening_months:
            return True
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            if month not in self.opening_months:
                return False
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return True


def normalize_tags(tags: Iterable[str]) -> tuple[str, ...]:
    """Lowercase section:tag, no duplicates. Empty tags are allowed."""
    kept: list[str] = []
    for raw in tags:
        tag = raw.strip().lower()
        if not tag:
            continue
        if not _is_catalog_tag(tag):
            raise InvalidOffer("tags must be section:tag")
        if tag not in kept:
            kept.append(tag)
    return tuple(kept)


# Same ids as the panel builder accepts (wishes/infrastructure/llm/panel_builder.py, Slug).
_ID = r"[a-z0-9]+(?:[_-][a-z0-9]+)*"
_CATALOG_TAG = re.compile(rf"{_ID}:{_ID}")


def _is_catalog_tag(tag: str) -> bool:
    return _CATALOG_TAG.fullmatch(tag) is not None
