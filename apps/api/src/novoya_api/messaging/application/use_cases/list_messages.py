from uuid import UUID

from novoya_api.messaging.application.ports.messages import MessageRepository, Plans, Wishes
from novoya_api.messaging.application.use_cases.access import check_access
from novoya_api.messaging.domain.message import Message, Side


class ListMessages:
    """The conversation of a wish, for its client, the admins, or an agent on its plan (see
    domain.message.may_read). Anyone else: not found."""

    def __init__(self, messages: MessageRepository, wishes: Wishes, plans: Plans) -> None:
        self._messages = messages
        self._wishes = wishes
        self._plans = plans

    async def __call__(self, wish_id: UUID, reader_id: UUID, side: Side) -> list[Message]:
        await check_access(self._wishes, self._plans, wish_id, reader_id, side)
        return await self._messages.list_for_wish(wish_id)
