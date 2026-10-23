from uuid import UUID

from novoya_api.messaging.application.ports.messages import Plans, Wishes
from novoya_api.messaging.domain.errors import ConversationNotFound
from novoya_api.messaging.domain.message import Side, may_read


async def check_access(
    wishes: Wishes, plans: Plans, wish_id: UUID, reader_id: UUID, side: Side
) -> None:
    """Raise ConversationNotFound unless the caller may read and write this wish's chat."""
    owner_id = await wishes.owner_id(wish_id)
    # Only an agent needs the plans: the owner and the admins pass without them.
    needs_plans = side is Side.AGENT and owner_id is not None and owner_id != reader_id
    wish_plans = await plans.of_wish(wish_id) if needs_plans else []
    if not may_read(owner_id, reader_id, side, wish_plans):
        raise ConversationNotFound("no such conversation")
