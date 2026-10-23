from uuid import UUID

from novoya_api.messaging.application.ports.messages import MessageRepository, Wishes
from novoya_api.messaging.domain.errors import ConversationNotFound
from novoya_api.messaging.domain.message import Message, may_read


class ListMessages:
    """The conversation of a wish, for its client or staff. Anyone else: not found."""

    def __init__(self, messages: MessageRepository, wishes: Wishes) -> None:
        self._messages = messages
        self._wishes = wishes

    async def __call__(self, wish_id: UUID, reader_id: UUID, staff: bool) -> list[Message]:
        if not may_read(await self._wishes.owner_id(wish_id), reader_id, staff):
            raise ConversationNotFound("no such conversation")
        return await self._messages.list_for_wish(wish_id)
