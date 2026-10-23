from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True)
class Client:
    """Who sent a wish, as the admin lists show them: the same as the admin users page."""

    user_id: UUID
    name: str | None
    email: str


@dataclass(frozen=True)
class AdminWishView:
    """One wish in the admin overview. client is None when the account is gone."""

    id: UUID
    status: str
    text: str
    country: str | None
    city: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime
    client: Client | None


@dataclass(frozen=True)
class PanelLimits:
    """What the destination's listed offers can serve from today on (#183): the panel's
    travellers stepper and date fields offer only these."""

    persons_min: int
    persons_max: int
    first_date: date
    last_date: date
    open_months: tuple[int, ...]


@dataclass(frozen=True)
class PanelLimitsView:
    """The limits (None when no listed offer is left there) and, when the client gave the
    travellers and both dates, whether at least one offer fits them (else None)."""

    limits: PanelLimits | None
    fits: bool | None
