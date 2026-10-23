"""Composition root of the messaging module: plugs the adapters into the use cases.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes.
"""

from typing import Annotated, NamedTuple
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import CurrentUser, Role
from novoya_api.messaging.application.use_cases.list_messages import ListMessages
from novoya_api.messaging.application.use_cases.post_message import PostMessage
from novoya_api.messaging.infrastructure.db.repository import SqlMessageRepository
from novoya_api.messaging.infrastructure.wishes import ModuleWishes
from novoya_api.shared.infrastructure.db.session import get_session
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from novoya_api.shared.infrastructure.system_clock import SystemClock

STAFF = (Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN)


class Participant(NamedTuple):
    user_id: UUID
    staff: bool  # an agent, an admin or a super admin reads every conversation


def get_participant(user: CurrentUser) -> Participant:
    """Whoever is signed in: 401 without a session. The use case decides what they may read."""
    return Participant(user.user_id.value, user.role in STAFF)


def get_list_messages(session: Annotated[AsyncSession, Depends(get_session)]) -> ListMessages:
    return ListMessages(messages=SqlMessageRepository(session), wishes=ModuleWishes(session))


def get_post_message(session: Annotated[AsyncSession, Depends(get_session)]) -> PostMessage:
    return PostMessage(
        messages=SqlMessageRepository(session),
        wishes=ModuleWishes(session),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
    )
