from uuid import UUID

from novoya_api.messaging.application.ports.messages import MessageRepository, Wishes
from novoya_api.messaging.domain.errors import ConversationNotFound
from novoya_api.messaging.domain.message import Message, may_read
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork


class PostMessage:
    """The client or a staff member writes in the conversation of a wish."""

    def __init__(
        self, messages: MessageRepository, wishes: Wishes, uow: UnitOfWork, clock: Clock
    ) -> None:
        self._messages = messages
        self._wishes = wishes
        self._uow = uow
        self._clock = clock

    async def __call__(self, wish_id: UUID, author_id: UUID, staff: bool, body: str) -> Message:
        if not may_read(await self._wishes.owner_id(wish_id), author_id, staff):
            raise ConversationNotFound("no such conversation")
        message = Message.write(wish_id, author_id, staff, body, self._clock.now())
        await self._messages.add(message)
        await self._uow.commit()
        return message
