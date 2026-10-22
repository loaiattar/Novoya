from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from novoya_api.wishes.application.dto import AdminWishView
from novoya_api.wishes.application.ports.planner import ProposedPlan
from novoya_api.wishes.application.use_cases.send_wish import SendWishResult
from novoya_api.wishes.domain.answers import Answers, SelectedTag
from novoya_api.wishes.domain.panel import Panel
from novoya_api.wishes.domain.wish import Destination


class SendWishRequest(BaseModel):
    # No control characters: PostgreSQL rejects NUL, and the rest is never part of a wish.
    text: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=1000,
            pattern=r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*$",
        ),
    ]


class DestinationOut(BaseModel):
    country: str
    city: str | None

    @classmethod
    def of(cls, destination: Destination) -> "DestinationOut":
        return cls(country=destination.country, city=destination.city)


class TagOut(BaseModel):
    id: str
    label: str
    preselected: bool


class PanelSectionOut(BaseModel):
    id: str
    title: str
    multi: bool
    tags: list[TagOut]


class PanelOut(BaseModel):
    """The preference panel (ARCHITECTURE.md section 3). Render it with generic components."""

    sections: list[PanelSectionOut]
    ask_budget: bool
    ask_persons: bool
    ask_dates: bool

    @classmethod
    def of(cls, panel: Panel) -> "PanelOut":
        return cls.model_validate(panel.to_dict())


class WishResponse(BaseModel):
    """panel_shown: show the panel. not_covered: we don't go there, offer the suggestions.
    draft: the text names no place, ask where, with the suggestions as choices."""

    id: UUID
    status: Literal["draft", "not_covered", "panel_shown"]
    destination: DestinationOut | None
    panel: PanelOut | None
    suggestions: list[DestinationOut]

    @classmethod
    def of(cls, result: SendWishResult) -> "WishResponse":
        wish = result.wish
        return cls(
            id=wish.id,
            status=wish.status.value,
            destination=DestinationOut.of(wish.destination) if wish.destination else None,
            panel=PanelOut.of(wish.panel) if wish.panel else None,
            suggestions=[DestinationOut.of(d) for d in result.suggestions],
        )


PanelId = Annotated[str, StringConstraints(min_length=1, max_length=100)]


class SelectedTagIn(BaseModel):
    """A tag of the panel, by the ids it was shown with."""

    section: PanelId
    tag: PanelId


class AnswerPanelRequest(BaseModel):
    """The panel answers. Every tag must come from the panel shown; no tags is allowed."""

    selected_tags: Annotated[list[SelectedTagIn], Field(max_length=100)]
    # Fits the budget_max column, NUMERIC(10, 2).
    budget_max: Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
    currency: Literal["EUR"] = "EUR"  # quotes are in euros (#27)
    persons: Annotated[int, Field(ge=1, le=50)]
    start_date: date
    end_date: date  # after start_date: checked by the domain, 422 invalid_answers

    def to_answers(self) -> Answers:
        return Answers(
            selected_tags=tuple(SelectedTag(t.section, t.tag) for t in self.selected_tags),
            budget_max=self.budget_max,
            currency=self.currency,
            persons=self.persons,
            start_date=self.start_date,
            end_date=self.end_date,
        )


class PlanItemOut(BaseModel):
    id: UUID
    offer_id: UUID
    day: int
    quantity: int
    note: str | None
    kind: str
    title: str
    description: str


class PlanResponse(BaseModel):
    """The proposed plan, day by day. No price until it is quoted and no partner name.
    based_on_preferences is false when the client picked no tag."""

    id: UUID
    wish_id: UUID
    status: Literal["proposed"]
    based_on_preferences: bool
    summary: str
    items: list[PlanItemOut]

    @classmethod
    def of(cls, plan: ProposedPlan) -> "PlanResponse":
        return cls(
            id=plan.id,
            wish_id=plan.wish_id,
            status=plan.status,
            based_on_preferences=plan.based_on_preferences,
            summary=plan.summary,
            items=[PlanItemOut.model_validate(item, from_attributes=True) for item in plan.items],
        )


WishStatusName = Literal["draft", "not_covered", "panel_shown", "answered", "planned"]


class WishClient(BaseModel):
    """Who sent it: name and email, as on the admin users page."""

    id: UUID
    name: str | None
    email: str


class AdminWish(BaseModel):
    """One wish in the admin overview. client is null when the account is gone."""

    id: UUID
    status: WishStatusName
    text: str
    country: str | None
    city: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime
    client: WishClient | None

    @classmethod
    def of(cls, view: AdminWishView) -> "AdminWish":
        client = view.client
        return cls(
            id=view.id,
            status=view.status,
            text=view.text,
            country=view.country,
            city=view.city,
            persons=view.persons,
            start_date=view.start_date,
            end_date=view.end_date,
            created_at=view.created_at,
            updated_at=view.updated_at,
            client=WishClient(id=client.user_id, name=client.name, email=client.email)
            if client
            else None,
        )
