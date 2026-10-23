from typing import Protocol
from uuid import UUID

from novoya_api.messaging.domain.message import Message

# The newest messages a conversation shows. A chat about one trip stays far below it.
CONVERSATION_CAP = 500


class MessageRepository(Protocol):
    async def list_for_wish(self, wish_id: UUID) -> list[Message]:
        """The messages of this wish, oldest first, at most the CONVERSATION_CAP newest."""
        ...

    async def add(self, message: Message) -> None: ...


class Wishes(Protocol):
    async def owner_id(self, wish_id: UUID) -> UUID | None:
        """The client who sent the wish, or None when there is no such wish."""
        ...
