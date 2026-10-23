from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from novoya_api.quoting.domain.quote import Quote, QuoteStatus
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
class QuoteTrip:
    """Where and when the quoted trip goes, as the quote email says it."""

    country: str | None
    city: str | None
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class QuoteEmail:
    """The email telling the client their quote is in their account. It holds no PDF, no price
    and no partner: the client reads those after signing in."""

    to: str
    name: str | None
    locale: Locale
    trip: QuoteTrip
    quote_url: str


@dataclass(frozen=True)
class QuoteView:
    """A sent quote, without its PDF. email_sent is False when the client's email did not go
    out: the quote is saved anyway and the agent can send the email again."""

    id: UUID
    number: str
    plan_id: UUID
    total: Decimal
    currency: str
    locale: str
    sent_at: datetime
    valid_until: datetime
    email_sent: bool = False

    @classmethod
    def of(cls, quote: Quote, email_sent: bool = False) -> "QuoteView":
        return cls(
            id=quote.id,
            number=quote.number,
            plan_id=quote.plan_id,
            total=quote.total,
            currency=quote.currency,
            locale=quote.locale.value,
            sent_at=quote.sent_at,
            valid_until=quote.valid_until,
            email_sent=email_sent,
        )


@dataclass(frozen=True)
class PlanQuoteView:
    """A sent quote as its agent follows it: where it stands, and the client's answer and
    comment once they gave them."""

    quote: QuoteView
    status: QuoteStatus
    decided_at: datetime | None
    client_comment: str | None


@dataclass(frozen=True)
class QuoteDetailView:
    """A quote as its reader sees it, without its PDF: where it stands, the client's answer,
    who prepared it and the trip with its priced lines. The trip fields are empty and the
    lines too when the plan is gone."""

    id: UUID
    number: str
    plan_id: UUID
    total: Decimal
    currency: str
    locale: str
    sent_at: datetime
    valid_until: datetime
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
    items: tuple[QuotedItem, ...]
    extras: tuple[QuotedExtra, ...]

    @classmethod
    def at(
        cls,
        quote: Quote,
        status: QuoteStatus,
        plan: QuotedPlan | None,
        agent: Person | None,
    ) -> "QuoteDetailView":
        return cls(
            id=quote.id,
            number=quote.number,
            plan_id=quote.plan_id,
            total=quote.total,
            currency=quote.currency,
            locale=quote.locale.value,
            sent_at=quote.sent_at,
            valid_until=quote.valid_until,
            status=status,
            decided_at=quote.decided_at,
            client_comment=quote.client_comment,
            agent_name=agent.name if agent else None,
            country=plan.country if plan else None,
            city=plan.city if plan else None,
            start_date=plan.start_date if plan else None,
            end_date=plan.end_date if plan else None,
            persons=plan.persons if plan else None,
            budget_max=plan.budget_max if plan else None,
            items=plan.items if plan else (),
            extras=plan.extras if plan else (),
        )


@dataclass(frozen=True)
class QuotePdf:
    filename: str
    content: bytes


@dataclass(frozen=True)
class AdminQuoteView:
    """One quote in the admin overview, without its PDF. client is None when the account is
    gone."""

    id: UUID
    number: str
    plan_id: UUID
    status: str
    total: Decimal
    currency: str
    locale: str
    sent_at: datetime
    valid_until: datetime
    trip: QuoteTrip
    client: Person | None
