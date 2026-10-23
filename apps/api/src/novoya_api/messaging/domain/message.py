from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from novoya_api.messaging.domain.errors import InvalidMessage

MAX_LENGTH = 2000


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


def may_read(owner_id: UUID | None, reader_id: UUID, staff: bool) -> bool:
    """Only the client who sent the wish and the agency's staff read its conversation."""
    return owner_id is not None and (staff or owner_id == reader_id)
