from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from novoya_api.quoting.domain.quote import Quote
from novoya_api.shared.domain.value_objects import Locale


@dataclass(frozen=True)
class QuotedItem:
    """A kept item on the quote: what, which day, how many, its price. Never the partner."""

    day: int
    kind: str | None
    title: str | None
    description: str | None
    quantity: int
    price: Decimal


@dataclass(frozen=True)
class QuotedExtra:
    """An extra on the quote. price is None for an included extra."""

    label: str
    unit: str
    pricing: str
    price: Decimal | None


@dataclass(frozen=True)
class QuotedPlan:
    """The plan planning just marked quoted, with what the PDF shows. tags are "section:tag"."""

    plan_id: UUID
    wish_id: UUID
    client_id: UUID
    agent_id: UUID
    summary: str
    items: tuple[QuotedItem, ...]
    extras: tuple[QuotedExtra, ...]
    total: Decimal
    wish_text: str
    country: str | None
    city: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    budget_max: Decimal | None
    currency: str | None
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Person:
    """The client or the agent, as the quote names them."""

    user_id: UUID
    name: str | None
    email: str
    locale: Locale


@dataclass(frozen=True)
class QuoteDocument:
    """Everything the PDF shows. answer_url opens the quote in the web app."""

    quote: Quote
    plan: QuotedPlan
    client: Person
    agent: Person
    answer_url: str


@dataclass(frozen=True)
class QuoteView:
    """A sent quote, without its PDF."""

    id: UUID
    number: str
    plan_id: UUID
    total: Decimal
    currency: str
    locale: str
    sent_at: datetime
    valid_until: datetime

    @classmethod
    def of(cls, quote: Quote) -> "QuoteView":
        return cls(
            quote.id,
            quote.number,
            quote.plan_id,
            quote.total,
            quote.currency,
            quote.locale.value,
            quote.sent_at,
            quote.valid_until,
        )


@dataclass(frozen=True)
class QuotePdf:
    filename: str
    content: bytes
