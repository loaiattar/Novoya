from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from novoya_api.quoting.application.dto import AdminQuoteView, QuoteDetailView, QuoteView
from novoya_api.quoting.domain.quote import COMMENT_MAX_LENGTH, QuoteStatus


class SendQuoteRequest(BaseModel):
    """The quote's language, chosen by the agent. Without it, the client's language."""

    locale: Literal["en", "fr"] | None = None


class QuoteFields(BaseModel):
    """The fields every view of a quote shares."""

    id: UUID
    number: str
    plan_id: UUID
    total: Decimal
    currency: str
    locale: Literal["en", "fr"]
    sent_at: datetime
    valid_until: datetime


class Quote(QuoteFields):
    """A sent quote. total is in currency (always EUR); the PDF is at GET /quotes/{id}/pdf.
    email_sent is false when the client's email did not go out: POST
    /agent/quotes/{id}/email sends it again."""

    email_sent: bool

    @classmethod
    def of(cls, view: QuoteView) -> "Quote":
        return cls.model_validate(view, from_attributes=True)


class QuoteItem(BaseModel):
    """A kept item on its day. title is null when the offer left the catalog. price is the
    line's price in EUR."""

    day: int
    kind: str | None
    title: str | None
    description: str | None
    quantity: int
    price: Decimal


class QuoteExtra(BaseModel):
    """An extra the client chose. price is null for an included extra."""

    label: str
    unit: str
    price: Decimal | None


class QuoteDetail(QuoteFields):
    """A quote and where it stands: open, expired once the validity day is over in Paris, or
    the client's answer (accepted, rejected) with decided_at and client_comment. With the
    trip and its priced lines, as the PDF shows them; those are null or empty when the plan
    is gone. Unlike the quote just sent, it has no email_sent: that only matters when it is
    sent."""

    status: QuoteStatus
    decided_at: datetime | None
    client_comment: str | None
    agent_name: str | None
    country: str | None
    city: str | None
    start_date: date | None
    end_date: date | None
    persons: int | None
    budget_max: Decimal | None
    items: list[QuoteItem]
    extras: list[QuoteExtra]

    @classmethod
    def of(cls, view: QuoteDetailView) -> "QuoteDetail":
        return cls.model_validate(view, from_attributes=True)


class AnswerQuoteRequest(BaseModel):
    """An optional comment for the agent with the answer."""

    comment: str | None = Field(default=None, max_length=COMMENT_MAX_LENGTH)


class QuoteClient(BaseModel):
    """Who the quote is for: name and email, as on the admin users page."""

    id: UUID
    name: str | None
    email: str


class AdminQuote(QuoteFields):
    """One quote in the admin overview, with the status GET /quotes/{id} gives it. The PDF
    is at GET /quotes/{id}/pdf."""

    status: QuoteStatus
    country: str | None
    city: str | None
    start_date: date | None
    end_date: date | None
    client: QuoteClient | None

    @classmethod
    def of(cls, view: AdminQuoteView) -> "AdminQuote":
        client = view.client
        return cls(
            id=view.id,
            number=view.number,
            plan_id=view.plan_id,
            status=view.status,
            total=view.total,
            currency=view.currency,
            locale=view.locale,
            sent_at=view.sent_at,
            valid_until=view.valid_until,
            country=view.trip.country,
            city=view.trip.city,
            start_date=view.trip.start_date,
            end_date=view.trip.end_date,
            client=QuoteClient(id=client.user_id, name=client.name, email=client.email)
            if client
            else None,
        )
