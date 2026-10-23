from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from novoya_api.catalog.public import OfferKind
from novoya_api.planning.application.dto import (
    AdminPlanEntryView,
    AdminPlanView,
    AgentPlanView,
    Person,
    PlanView,
    QueueEntryView,
)
from novoya_api.planning.domain.plan import PlanStatus


class PlanItemResponse(BaseModel):
    id: UUID
    offer_id: UUID
    day: int
    quantity: int
    note: str | None
    kind: OfferKind | None
    title: str | None
    description: str | None
    available: bool


class Plan(BaseModel):
    """The plan day by day. Never a price: the quote has it. Never a partner name."""

    id: UUID
    wish_id: UUID
    status: PlanStatus
    based_on_preferences: bool
    summary: str
    items: list[PlanItemResponse]
    answer_within_days: int = Field(
        description="Days within which the agency answers once the trip is sent (a setting)."
    )

    @classmethod
    def of(cls, plan: PlanView, answer_within_days: int) -> "Plan":
        return cls(
            answer_within_days=answer_within_days,
            id=plan.id,
            wish_id=plan.wish_id,
            status=plan.status,
            based_on_preferences=plan.based_on_preferences,
            summary=plan.summary,
            items=[
                PlanItemResponse.model_validate(item, from_attributes=True) for item in plan.items
            ],
        )


class QueueEntry(BaseModel):
    """A plan waiting for a quote. Wish text, place, dates, travellers and budget. No prices."""

    id: UUID
    wish_id: UUID
    status: PlanStatus
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

    @classmethod
    def of(cls, entry: QueueEntryView) -> "QueueEntry":
        return cls.model_validate(entry, from_attributes=True)


class AgentPlanItem(BaseModel):
    """One day for the assigned agent: negotiated price, and the partner to call."""

    id: UUID
    offer_id: UUID
    day: int
    quantity: int
    note: str | None
    kind: OfferKind | None
    title: str | None
    description: str | None
    available: bool
    negotiated_price: Decimal | None
    removed: bool
    partner_name: str | None
    partner_contact_email: str | None
    partner_contact_phone: str | None


class AgentPlanExtra(BaseModel):
    """An extra the client chose. price_eur: the supplement, or what the agent set; null for
    an included extra and for an on_quote extra not priced yet. needs_quantity_check: a
    supplement per person, night or day; its amount is counted once, so the agent checks the
    quantity and confirms it by setting its price, even the same one (confirmed)."""

    extra_id: UUID
    pricing: Literal["included", "supplement", "on_quote"]
    price_eur: Decimal | None
    label: str
    unit: str
    needs_quantity_check: bool
    confirmed: bool


class AgentPlan(BaseModel):
    """The plan as the assigned agent sees it. Prices, partners, running total and budget.
    total counts priced items and priced extras; ready_to_quote is false while a kept item or
    an on_quote extra has no price, or a supplement that needs a quantity check is not
    confirmed."""

    id: UUID
    wish_id: UUID
    status: PlanStatus
    summary: str
    assigned_agent_id: UUID | None
    items: list[AgentPlanItem]
    extras: list[AgentPlanExtra]
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

    @classmethod
    def of(cls, plan: AgentPlanView) -> "AgentPlan":
        return cls(
            id=plan.id,
            wish_id=plan.wish_id,
            status=plan.status,
            summary=plan.summary,
            assigned_agent_id=plan.assigned_agent_id,
            items=[AgentPlanItem.model_validate(item, from_attributes=True) for item in plan.items],
            extras=[
                AgentPlanExtra.model_validate(extra, from_attributes=True) for extra in plan.extras
            ],
            total=plan.total,
            ready_to_quote=plan.ready_to_quote,
            budget_max=plan.budget_max,
            currency=plan.currency,
            over_budget=plan.over_budget,
            wish_text=plan.wish_text,
            country=plan.country,
            city=plan.city,
            persons=plan.persons,
            start_date=plan.start_date,
            end_date=plan.end_date,
        )


class SetPlanItemRequest(BaseModel):
    """Set a negotiated price in EUR, or set removed. True drops the item, false puts it back."""

    negotiated_price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    removed: bool | None = None

    @model_validator(mode="after")
    def exactly_one_field(self) -> "SetPlanItemRequest":
        priced = self.negotiated_price is not None
        flagged = self.removed is not None
        if priced and flagged:
            raise ValueError("set a price or set removed, not both")
        if not priced and not flagged:
            raise ValueError("set a price or set removed")
        return self


class RequestQuoteRequest(BaseModel):
    """The extras the client adds to the plan. Without a body, none."""

    extra_ids: list[UUID] = Field(default_factory=list, max_length=50)


class SetPlanExtraRequest(BaseModel):
    """The price in EUR of an on_quote extra, or an adjusted supplement."""

    price_eur: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class PersonOut(BaseModel):
    """A client or an agent: name and email, as on the admin users page."""

    id: UUID
    name: str | None
    email: str

    @classmethod
    def of(cls, person: Person | None) -> "PersonOut | None":
        return cls(id=person.user_id, name=person.name, email=person.email) if person else None


class AdminPlanEntry(BaseModel):
    """One plan in the admin overview. No prices and no partner: GET /admin/plans/{id}.
    client or agent is null when the account is gone or nobody took the plan yet."""

    id: UUID
    wish_id: UUID
    status: PlanStatus
    summary: str
    created_at: datetime
    updated_at: datetime
    country: str | None
    city: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    client: PersonOut | None
    agent: PersonOut | None

    @classmethod
    def of(cls, entry: AdminPlanEntryView) -> "AdminPlanEntry":
        return cls(
            id=entry.id,
            wish_id=entry.wish_id,
            status=PlanStatus(entry.status),
            summary=entry.summary,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            country=entry.country,
            city=entry.city,
            persons=entry.persons,
            start_date=entry.start_date,
            end_date=entry.end_date,
            client=PersonOut.of(entry.client),
            agent=PersonOut.of(entry.agent),
        )


class AdminPlan(BaseModel):
    """One plan, read-only, for an admin: the agent's view, the client and the agent."""

    plan: AgentPlan
    client: PersonOut | None
    agent: PersonOut | None

    @classmethod
    def of(cls, view: AdminPlanView) -> "AdminPlan":
        return cls(
            plan=AgentPlan.of(view.plan),
            client=PersonOut.of(view.client),
            agent=PersonOut.of(view.agent),
        )
