"""Composition root of the messaging module: plugs the adapters into the use cases.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes.
"""

from functools import lru_cache
from typing import Annotated, NamedTuple
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import CurrentUser, Role
from novoya_api.messaging.application.use_cases.list_messages import ListMessages
from novoya_api.messaging.application.use_cases.post_message import PostMessage
from novoya_api.messaging.domain.message import Side
from novoya_api.messaging.infrastructure.db.repository import SqlMessageRepository
from novoya_api.messaging.infrastructure.plans import PlanningPlans
from novoya_api.messaging.infrastructure.wishes import ModuleWishes
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.infrastructure.db.session import get_session
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from novoya_api.shared.infrastructure.system_clock import SystemClock

SIDES = {Role.AGENT: Side.AGENT, Role.ADMIN: Side.ADMIN, Role.SUPER_ADMIN: Side.ADMIN}


class Participant(NamedTuple):
    user_id: UUID
    side: Side


def get_participant(user: CurrentUser) -> Participant:
    """Whoever is signed in: 401 without a session. The use case decides what they may read."""
    return Participant(user.user_id.value, SIDES.get(user.role, Side.CLIENT))


# Built once: the counters must outlive the request (too_many_requests, 429).
@lru_cache
def get_rate_limiter() -> RateLimiter:
    return InMemoryRateLimiter(SystemClock())


def get_list_messages(session: Annotated[AsyncSession, Depends(get_session)]) -> ListMessages:
    return ListMessages(
        messages=SqlMessageRepository(session),
        wishes=ModuleWishes(session),
        plans=PlanningPlans(session),
    )


def get_post_message(
    session: Annotated[AsyncSession, Depends(get_session)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> PostMessage:
    return PostMessage(
        messages=SqlMessageRepository(session),
        wishes=ModuleWishes(session),
        plans=PlanningPlans(session),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
        rate_limiter=rate_limiter,
    )
