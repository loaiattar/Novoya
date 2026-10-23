from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from novoya_api.messaging.domain.message import Message


class PostMessageRequest(BaseModel):
    # The domain trims and checks 1 to 2000 characters (422 invalid_message); this bound
    # only stops a huge body before the use case sees it.
    body: str = Field(max_length=8000)


class ChatMessage(BaseModel):
    id: UUID
    body: str
    from_agency: bool  # written by an agent or an admin: the client sees "the agency"
    mine: bool  # written by the caller
    sent_at: datetime

    @classmethod
    def of(cls, message: Message, reader_id: UUID) -> "ChatMessage":
        return cls(
            id=message.id,
            body=message.body,
            from_agency=message.from_agency,
            mine=message.author_id == reader_id,
            sent_at=message.sent_at,
        )
