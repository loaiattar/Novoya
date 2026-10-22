from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from novoya_api.quoting.application.dto import QuoteDetailView, QuoteView


class SendQuoteRequest(BaseModel):
    """The quote's language, chosen by the agent. Without it, the client's language."""

    locale: Literal["en", "fr"] | None = None


class Quote(BaseModel):
    """A sent quote. total is in currency (always EUR); the PDF is at GET /quotes/{id}/pdf.
    email_sent is false when the client's email did not go out: POST
    /agent/quotes/{id}/email sends it again."""

    id: UUID
    number: str
    plan_id: UUID
    total: Decimal
    currency: str
    locale: Literal["en", "fr"]
    sent_at: datetime
    valid_until: datetime
    email_sent: bool

    @classmethod
    def of(cls, view: QuoteView) -> "Quote":
        return cls.model_validate(view, from_attributes=True)


class QuoteDetail(BaseModel):
    """A quote and where it stands: open, or expired once the validity date has passed.
    Unlike the quote just sent, it has no email_sent: that only matters when it is sent."""

    id: UUID
    number: str
    plan_id: UUID
    total: Decimal
    currency: str
    locale: Literal["en", "fr"]
    sent_at: datetime
    valid_until: datetime
    status: Literal["open", "expired"]

    @classmethod
    def detail(cls, view: QuoteDetailView) -> "QuoteDetail":
        quote = view.quote
        return cls(
            id=quote.id,
            number=quote.number,
            plan_id=quote.plan_id,
            total=quote.total,
            currency=quote.currency,
            locale=quote.locale,
            sent_at=quote.sent_at,
            valid_until=quote.valid_until,
            status=view.status,
        )
