from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from novoya_api.wishes.domain.wish import Wish


@dataclass(frozen=True)
class ProposedItem:
    id: UUID
    offer_id: UUID
    day: int
    quantity: int
    note: str | None
    kind: str
    title: str
    description: str
    available: bool = True


@dataclass(frozen=True)
class ProposedPlan:
    """The plan built from an answered wish: no price, no partner name."""

    id: UUID
    wish_id: UUID
    status: str
    based_on_preferences: bool
    summary: str
    items: tuple[ProposedItem, ...]


@dataclass(frozen=True)
class CustomRequest:
    """The plan of a wish sent to the agency although no offer fits it (#184): requested,
    with no item until an agent builds it."""

    id: UUID
    wish_id: UUID
    status: str


class Planner(Protocol):
    async def propose(self, wish: Wish) -> ProposedPlan:
        """Build and add the plan of an answered wish; the caller commits. Raises a domain
        error (422) when no offer fits the travellers and dates."""
        ...

    async def request_custom(self, wish: Wish) -> CustomRequest:
        """Add the custom plan of an answered wish, sent to the agency as it is; the caller
        commits. Like propose, call it before writing: a model may run first."""
        ...

    async def confirm(self, plan_id: UUID, user_id: UUID) -> None:
        """After the commit: email the client that the agency has the trip. Never raises."""
        ...
