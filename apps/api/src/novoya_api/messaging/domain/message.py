from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novoya_api.messaging.domain.errors import InvalidMessage

MAX_LENGTH = 2000

# A plan the agents' queue shows: requested and not taken yet (as planning's queue).
REQUESTED = "requested"


class Side(StrEnum):
    """What the caller is, for the chat's read rule."""

    CLIENT = "client"
    AGENT = "agent"
    ADMIN = "admin"  # an admin or a super admin


@dataclass(frozen=True)
class WishPlan:
    """A plan of the wish, as far as the read rule needs it."""

    status: str
    assigned_agent_id: UUID | None


@dataclass(frozen=True)
class Message:
    """One line of the conversation of a wish. from_agency is true when a staff member wrote
    it: the client sees "the agency", not which agent."""

    id: UUID
    wish_id: UUID
    author_id: UUID | None  # None once the author's account is erased
    from_agency: bool
    body: str
    sent_at: datetime

    @classmethod
    def write(
        cls, wish_id: UUID, author_id: UUID, from_agency: bool, body: str, now: datetime
    ) -> "Message":
        text = body.strip()
        if not text:
            raise InvalidMessage("the message is empty")
        if len(text) > MAX_LENGTH:
            raise InvalidMessage(f"the message is longer than {MAX_LENGTH} characters")
        return cls(uuid4(), wish_id, author_id, from_agency, text, now)


def agent_may_read(agent_id: UUID, plans: Iterable[WishPlan]) -> bool:
    """An agent reads the chat of a wish whose plan waits in the queue (requested, nobody
    took it), or whose plan they took, the same plans GET /agent/plans lets them see. No plan,
    or a proposed one: not them."""
    return any(
        plan.assigned_agent_id == agent_id
        or (plan.status == REQUESTED and plan.assigned_agent_id is None)
        for plan in plans
    )


def may_read(
    owner_id: UUID | None, reader_id: UUID, side: Side, plans: Iterable[WishPlan] = ()
) -> bool:
    """The client who sent the wish and the admins always; an agent per agent_may_read."""
    if owner_id is None:
        return False
    if owner_id == reader_id or side is Side.ADMIN:
        return True
    return side is Side.AGENT and agent_may_read(reader_id, plans)
