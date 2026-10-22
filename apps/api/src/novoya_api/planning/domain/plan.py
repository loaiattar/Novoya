import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from novoya_api.planning.domain.errors import InvalidPlan, PlanNotFound, PlanNotReady
from novoya_api.shared.domain.errors import InvalidTransition, PermissionDenied


class PlanStatus(StrEnum):
    PROPOSED = "proposed"
    REQUESTED = "requested"
    NEGOTIATING = "negotiating"
    QUOTED = "quoted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class DraftItem:
    """An item the model (or the fallback) proposes, not yet checked against the catalog."""

    offer_id: UUID
    day: int
    quantity: int
    note: str | None


@dataclass(frozen=True, slots=True)
class PlanItem:
    """One offer on one day of the trip. No price until an agent negotiates it."""

    id: UUID
    offer_id: UUID
    day: int
    quantity: int
    note: str | None
    negotiated_price: Decimal | None = None
    removed: bool = False


@dataclass(frozen=True, slots=True)
class PlanExtra:
    """An extra the client chose when asking for the quote (a quiet room, a private guide).

    pricing is the catalog's: included, supplement or on_quote. price_eur is the supplement
    as it was then (counted once, the agent can adjust it) or the price the agent got for an
    on_quote extra; None until then. An included extra has no price. label and unit are
    copied too, so the agent knows what was asked even if the catalog changes; they are not
    part of what makes two choices equal.

    A supplement per person, night or day is still counted once: the agent checks how many
    the trip needs and confirms the price (confirmed), even if it stays the same."""

    extra_id: UUID
    pricing: str
    price_eur: Decimal | None
    label: str = field(default="", compare=False)
    unit: str = field(default="", compare=False)
    confirmed: bool = field(default=False, compare=False)

    @property
    def needs_quantity_check(self) -> bool:
        """A supplement whose unit depends on the travellers or the nights (par personne,
        par nuit, par jour...): its amount is for one, so the agent decides the total."""
        return self.pricing == "supplement" and _unit_key(self.unit) in PER_QUANTITY_UNITS


EXTRA_PRICINGS = ("included", "supplement", "on_quote")


def _unit_key(unit: str) -> str:
    """Case, accents and spaces ignored: "Par  Demi-Journée" -> "par demi-journee"."""
    plain = "".join(
        char for char in unicodedata.normalize("NFKD", unit) if not unicodedata.combining(char)
    )
    return " ".join(plain.split()).casefold()


# The units of DÉTOUR's preferences that multiply with the group or the trip's length, and
# their English forms. A fixed list: a unit nobody listed is counted once, as before.
PER_QUANTITY_UNITS = frozenset(
    {
        "par personne",
        "par personne et nuit",
        "par nuit",
        "par jour",
        "par demi-journee",
        "per person",
        "per person per night",
        "per person/night",
        "per night",
        "per day",
        "per half-day",
    }
)


def keep_valid(drafts: Sequence[DraftItem], allowed: set[UUID], trip_days: int) -> list[DraftItem]:
    """The drafts that point to an allowed offer, on a day of the trip, in their order.

    The model chooses the offer ids, so an id it invented or an offer that does not fit the
    group or the dates never reaches the plan."""
    return [
        draft
        for draft in drafts
        if draft.offer_id in allowed and 1 <= draft.day <= trip_days and draft.quantity >= 1
    ]


def tidy(drafts: Sequence[DraftItem], hotels: set[UUID], trip_days: int) -> list[DraftItem]:
    """The valid drafts without repeats, and hotel nights that are each booked once.

    The model repeats itself: an offer is kept once a day, a hotel once in the whole trip. A
    hotel night runs from its day to the next, so the nights are 1 to trip_days - 1. A hotel
    keeps its free nights from its day on, up to the first night another hotel already has,
    and is dropped when its first night is taken: an agent would otherwise quote nights no
    one sleeps."""
    kept: list[DraftItem] = []
    seen: set[tuple[UUID, int | None]] = set()
    booked: set[int] = set()
    for draft in drafts:
        key = (draft.offer_id, None if draft.offer_id in hotels else draft.day)
        if key in seen:
            continue
        seen.add(key)
        if draft.offer_id in hotels:
            nights = 0
            for night in range(draft.day, min(draft.day + draft.quantity, trip_days)):
                if night in booked:
                    break
                nights += 1
            if nights == 0:
                continue
            booked.update(range(draft.day, draft.day + nights))
            draft = replace(draft, quantity=nights)
        kept.append(draft)
    return kept


@dataclass(slots=True)
class Plan:
    """The trip built from partner offers, day by day. It starts proposed, with no price:
    the client asks for a quote, then an agent negotiates each item."""

    id: UUID
    wish_id: UUID
    status: PlanStatus
    based_on_preferences: bool
    summary: str
    items: tuple[PlanItem, ...]
    created_at: datetime
    updated_at: datetime
    assigned_agent_id: UUID | None = None
    extras: tuple[PlanExtra, ...] = ()

    @classmethod
    def propose(
        cls,
        wish_id: UUID,
        based_on_preferences: bool,
        summary: str,
        drafts: Sequence[DraftItem],
        trip_days: int,
        now: datetime,
    ) -> "Plan":
        if not drafts:
            raise InvalidPlan("a plan needs at least one item")
        for draft in drafts:
            if not 1 <= draft.day <= trip_days:
                raise InvalidPlan(f"day {draft.day} is outside the {trip_days}-day trip")
            if draft.quantity < 1:
                raise InvalidPlan("the quantity must be at least 1")
        items = tuple(
            PlanItem(uuid4(), draft.offer_id, draft.day, draft.quantity, draft.note)
            for draft in sorted(drafts, key=lambda draft: draft.day)
        )
        return cls(
            uuid4(), wish_id, PlanStatus.PROPOSED, based_on_preferences, summary, items, now, now
        )

    def request_quote(self, now: datetime, extras: Sequence[PlanExtra] = ()) -> None:
        """The client asks an agent to price this plan, with the extras they chose. Only from
        proposed: the extras are fixed from then on, only their prices change."""
        if self.status is not PlanStatus.PROPOSED:
            raise InvalidTransition("the plan is not proposed")
        if len({extra.extra_id for extra in extras}) != len(extras):
            raise InvalidPlan("an extra is chosen twice")
        for extra in extras:
            if extra.pricing not in EXTRA_PRICINGS:
                raise InvalidPlan("unknown extra pricing")
        self.extras = tuple(extras)
        self.status = PlanStatus.REQUESTED
        self.updated_at = now

    def take(self, agent_id: UUID, now: datetime) -> None:
        """An agent claims this plan to negotiate prices. Only from requested."""
        if self.status is not PlanStatus.REQUESTED:
            raise InvalidTransition("the plan is not requested")
        self.status = PlanStatus.NEGOTIATING
        self.assigned_agent_id = agent_id
        self.updated_at = now

    def set_item_price(self, item_id: UUID, by: UUID, price: Decimal, now: datetime) -> None:
        """The assigned agent sets the negotiated price of one kept item. Only while negotiating."""
        self._must_be_assigned(by)
        if price <= 0:
            raise InvalidPlan("the price must be more than 0")
        item = self._item(item_id)
        if item.removed:
            raise InvalidPlan("a removed item has no price")
        self.items = tuple(
            replace(entry, negotiated_price=price) if entry.id == item_id else entry
            for entry in self.items
        )
        self.updated_at = now

    def remove_item(self, item_id: UUID, by: UUID, now: datetime) -> None:
        """The assigned agent drops an item so it is not quoted. At least one item must stay."""
        self._must_be_assigned(by)
        item = self._item(item_id)
        if item.removed:
            return
        kept = sum(1 for entry in self.items if not entry.removed)
        if kept <= 1:
            raise InvalidPlan("a plan needs at least one item")
        self.items = tuple(
            replace(entry, removed=True, negotiated_price=None) if entry.id == item_id else entry
            for entry in self.items
        )
        self.updated_at = now

    def restore_item(self, item_id: UUID, by: UUID, now: datetime) -> None:
        """The assigned agent puts a dropped item back. It has no price until they set one."""
        self._must_be_assigned(by)
        item = self._item(item_id)
        if not item.removed:
            return
        self.items = tuple(
            replace(entry, removed=False) if entry.id == item_id else entry for entry in self.items
        )
        self.updated_at = now

    def set_extra_price(self, extra_id: UUID, by: UUID, price: Decimal, now: datetime) -> None:
        """The assigned agent prices an on_quote extra or adjusts a supplement. Setting a
        price, even the same one, confirms the extra."""
        self._must_be_assigned(by)
        if price <= 0:
            raise InvalidPlan("the price must be more than 0")
        extra = self._extra(extra_id)
        if extra.pricing == "included":
            raise InvalidPlan("an included extra has no price")
        self.extras = tuple(
            replace(entry, price_eur=price, confirmed=True) if entry.extra_id == extra_id else entry
            for entry in self.extras
        )
        self.updated_at = now

    def mark_quoted(self, by: UUID, now: datetime) -> None:
        """The assigned agent sends the quote. Only while negotiating, and only once every
        price is in (ready_to_quote): the total is then final."""
        self._must_be_assigned(by)
        if not self.ready_to_quote():
            raise PlanNotReady("every kept item and extra needs its price before the quote")
        self.status = PlanStatus.QUOTED
        self.updated_at = now

    def priced_total(self) -> Decimal:
        """Kept items that already have a negotiated price, plus priced extras (each once).

        An on_quote extra without a price is not counted as 0: ready_to_quote() is false."""
        items = (
            item.negotiated_price
            for item in self.items
            if not item.removed and item.negotiated_price
        )
        extras = (
            extra.price_eur
            for extra in self.extras
            if extra.pricing != "included" and extra.price_eur is not None
        )
        return sum((*items, *extras), Decimal("0"))

    def ready_to_quote(self) -> bool:
        """Every kept item and every on_quote extra has a price, and the agent confirmed every
        supplement that needs a quantity check."""
        return (
            all(item.negotiated_price is not None for item in self.items if not item.removed)
            and all(
                extra.price_eur is not None for extra in self.extras if extra.pricing == "on_quote"
            )
            and all(extra.confirmed for extra in self.extras if extra.needs_quantity_check)
        )

    def _must_be_assigned(self, agent_id: UUID) -> None:
        if self.status is not PlanStatus.NEGOTIATING:
            raise InvalidTransition("the plan is not being negotiated")
        if self.assigned_agent_id != agent_id:
            raise PermissionDenied("only the assigned agent can price this plan")

    def _extra(self, extra_id: UUID) -> PlanExtra:
        for extra in self.extras:
            if extra.extra_id == extra_id:
                return extra
        raise PlanNotFound("no such extra on this plan")

    def _item(self, item_id: UUID) -> PlanItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise PlanNotFound("no such item")
