from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True)
class WishSummary:
    """One of the client's wishes, as the list of trips needs it."""

    wish_id: UUID
    text: str
    status: str
    country: str | None
    city: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    created_at: datetime


@dataclass(frozen=True)
class PlanSummary:
    plan_id: UUID
    status: str


@dataclass(frozen=True)
class TripView:
    """A wish and how far it has got: its plan and its quote, when they exist."""

    wish_id: UUID
    text: str
    status: str
    country: str | None
    city: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    created_at: datetime
    plan_id: UUID | None
    plan_status: str | None
    quote_id: UUID | None
