from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from novoya_api.trips.application.dto import TripView


class Trip(BaseModel):
    """A wish of the client and how far it has got."""

    wish_id: UUID
    text: str
    status: Literal["draft", "not_covered", "panel_shown", "answered", "planned"]
    country: str | None
    city: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    created_at: datetime
    plan_id: UUID | None
    plan_status: (
        Literal["proposed", "requested", "negotiating", "quoted", "accepted", "rejected"] | None
    )
    quote_id: UUID | None
    answer_within_days: int = Field(
        description="Days within which the agency answers once the trip is sent (a setting)."
    )

    @classmethod
    def of(cls, view: TripView, answer_within_days: int) -> "Trip":
        return cls(**vars(view), answer_within_days=answer_within_days)
