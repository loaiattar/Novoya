from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from novoya_api.shared.domain.value_objects import Locale


@dataclass(frozen=True)
class PlanRequest:
    """What the plan is built from: the answered wish. Tags are "section:tag"."""

    wish_id: UUID
    text: str
    country: str
    city: str | None
    tags: tuple[str, ...]
    persons: int
    start_date: date
    end_date: date
    budget_max: Decimal

    @property
    def trip_days(self) -> int:
        """The first and the last day both count."""
        return (self.end_date - self.start_date).days + 1


@dataclass(frozen=True)
class OfferSummary:
    """A listed offer as planning needs it: no partner and no price."""

    id: UUID
    kind: str
    title: str
    description: str
    tags: tuple[str, ...]
    featured: bool
    # From fitting_offers: the days of the trip it is open on (day 1 = the first day). A plan
    # places it only on those (#182). Empty for summaries_for, which only shows titles.
    open_days: frozenset[int] = frozenset()


@dataclass(frozen=True)
class ExtraSummary:
    """An active catalog extra as planning needs it. supplement_eur only for a supplement."""

    id: UUID
    label: str
    pricing: str
    supplement_eur: Decimal | None
    unit: str = ""


@dataclass(frozen=True)
class PlanItemView:
    """One day on the plan. available is false when the offer is gone from the catalog."""

    id: UUID
    offer_id: UUID
    day: int
    quantity: int
    note: str | None
    kind: str | None
    title: str | None
    description: str | None
    available: bool


@dataclass(frozen=True)
class PlanView:
    """The plan as the client sees it: never a price (the quote has it), never a partner name."""

    id: UUID
    wish_id: UUID
    status: str
    based_on_preferences: bool
    summary: str
    items: tuple[PlanItemView, ...]
    custom: bool = False  # sent to the agency although no offer fitted (#184)


@dataclass(frozen=True)
class OfferContact:
    """An offer as the agent needs it: titles plus the partner to call."""

    id: UUID
    kind: str
    title: str
    description: str
    partner_name: str
    partner_contact_email: str
    partner_contact_phone: str | None


@dataclass(frozen=True)
class TripBrief:
    """The wish as the quote queue shows it: text, place, dates, travellers, budget."""

    wish_id: UUID
    text: str
    country: str | None
    city: str | None
    budget_max: Decimal | None
    currency: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    tags: tuple[str, ...] = ()  # "section:tag", what the client clicked on the panel
    user_id: UUID | None = None  # the client who sent the wish


@dataclass(frozen=True)
class QueueEntryView:
    """One waiting plan in the agent's queue. No prices and no partner names."""

    id: UUID
    wish_id: UUID
    status: str
    summary: str
    updated_at: datetime
    wish_text: str
    country: str | None
    city: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    budget_max: Decimal | None
    currency: str | None
    custom: bool = False  # no offer fitted: the agent builds the plan (#184)


@dataclass(frozen=True)
class AgentPlanItemView:
    """One day on the agent's plan: prices, removed flag, and who to call."""

    id: UUID
    offer_id: UUID
    day: int
    quantity: int
    note: str | None
    kind: str | None
    title: str | None
    description: str | None
    available: bool
    negotiated_price: Decimal | None
    removed: bool
    partner_name: str | None
    partner_contact_email: str | None
    partner_contact_phone: str | None


@dataclass(frozen=True)
class AgentPlanExtraView:
    """An extra the client chose. price_eur: the supplement, or what the agent set; None for
    an included extra and for an on_quote extra not priced yet. needs_quantity_check: a
    supplement per person, night or day, counted once until the agent confirms its price
    (confirmed)."""

    extra_id: UUID
    pricing: str
    price_eur: Decimal | None
    label: str
    unit: str
    needs_quantity_check: bool
    confirmed: bool


@dataclass(frozen=True)
class AgentPlanView:
    """The plan as the assigned agent sees it: prices, partners, total and the client's budget.

    total counts priced items and priced extras; ready_to_quote is false while a kept item or
    an on_quote extra has no price, or a supplement that needs a quantity check is not
    confirmed."""

    id: UUID
    wish_id: UUID
    status: str
    summary: str
    assigned_agent_id: UUID | None
    items: tuple[AgentPlanItemView, ...]
    extras: tuple[AgentPlanExtraView, ...]
    total: Decimal
    ready_to_quote: bool
    budget_max: Decimal | None
    currency: str | None
    over_budget: bool
    wish_text: str | None
    country: str | None
    city: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    custom: bool = False
    # A model's idea of the trip from the client's text (#184): not from the catalog, no price.
    outline: str | None = None


@dataclass(frozen=True)
class AgentOfferView:
    """An offer the agent may add to the plan: it fits the trip's travellers and is open on
    open_days (day 1 = the trip's first day). With the partner, as on the agent's plan."""

    id: UUID
    kind: str
    title: str
    description: str
    partner_name: str
    open_days: tuple[int, ...]


@dataclass(frozen=True)
class TripDates:
    """Other dates for the same trip, the same length, when a plan can be built: from
    start_date to end_date, `offers` listed offers fit the group (#184)."""

    start_date: date
    end_date: date
    offers: int


@dataclass(frozen=True)
class PricedItem:
    """A kept item as the quote shows it: what, which day, how many, its price. No partner."""

    day: int
    kind: str | None
    title: str | None
    description: str | None
    quantity: int
    price: Decimal


@dataclass(frozen=True)
class PricedExtra:
    """An extra on the quote. price is None for an included extra."""

    label: str
    unit: str
    pricing: str
    price: Decimal | None


@dataclass(frozen=True)
class PricedPlan:
    """A quoted plan with everything the quote needs: the priced items and extras, the
    total, the trip and who it is for. Never a partner name."""

    plan_id: UUID
    wish_id: UUID
    client_id: UUID
    agent_id: UUID
    summary: str
    items: tuple[PricedItem, ...]
    extras: tuple[PricedExtra, ...]
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
class ClientContact:
    """Where to write to the client who sent the trip, and in which language."""

    email: str
    name: str | None
    locale: Locale


@dataclass(frozen=True)
class RequestReceivedEmail:
    """The email confirming the agency received the trip: when to expect an answer, and a
    link to the plan. No price and no partner."""

    to: str
    name: str | None
    locale: Locale
    plan_url: str
    answer_days: int


@dataclass(frozen=True)
class Person:
    """A client or an agent in the admin overview: name and email, as on the users page."""

    user_id: UUID
    name: str | None
    email: str


@dataclass(frozen=True)
class AdminPlanEntryView:
    """One plan in the admin overview. No prices and no partner: open the plan to see those.
    client or agent is None when the account is gone or nobody took the plan yet."""

    id: UUID
    wish_id: UUID
    status: str
    summary: str
    created_at: datetime
    updated_at: datetime
    country: str | None
    city: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    client: Person | None
    agent: Person | None


@dataclass(frozen=True)
class AdminPlanView:
    """One plan as the admin reads it: exactly what the agent sees, and who is involved."""

    plan: AgentPlanView
    client: Person | None
    agent: Person | None
