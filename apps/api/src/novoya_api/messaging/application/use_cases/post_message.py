from datetime import timedelta
from uuid import UUID

from novoya_api.messaging.application.ports.messages import MessageRepository, Plans, Wishes
from novoya_api.messaging.application.use_cases.access import check_access
from novoya_api.messaging.domain.message import Message, Side
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.application.unit_of_work import UnitOfWork

# Each author writes at most POST_LIMIT messages per POST_WINDOW (429 too_many_requests).
POST_LIMIT = 30
POST_WINDOW = timedelta(minutes=5)


class PostMessage:
    """The client, an admin or an agent on the wish's plan writes in its conversation."""

    def __init__(
        self,
        messages: MessageRepository,
        wishes: Wishes,
        plans: Plans,
        uow: UnitOfWork,
        clock: Clock,
        rate_limiter: RateLimiter,
    ) -> None:
        self._messages = messages
        self._wishes = wishes
        self._plans = plans
        self._uow = uow
        self._clock = clock
        self._rate_limiter = rate_limiter

    async def __call__(self, wish_id: UUID, author_id: UUID, side: Side, body: str) -> Message:
        await self._rate_limiter.hit(f"messages:post:{author_id}", POST_LIMIT, POST_WINDOW)
        await check_access(self._wishes, self._plans, wish_id, author_id, side)
        from_agency = side is not Side.CLIENT
        message = Message.write(wish_id, author_id, from_agency, body, self._clock.now())
        await self._messages.add(message)
        await self._uow.commit()
        return message
