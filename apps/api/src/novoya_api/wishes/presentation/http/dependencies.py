"""Composition root of the wishes module: plugs the adapters into the use cases.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes.
"""

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import CurrentUserView, require_client
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.infrastructure.db.session import get_session
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from novoya_api.shared.infrastructure.llm.client import get_orchestrator
from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.shared.infrastructure.llm.orchestrator import Orchestrator
from novoya_api.shared.infrastructure.system_clock import SystemClock
from novoya_api.wishes.application.ports.destination_reader import DestinationReader
from novoya_api.wishes.application.ports.panel_builder import PanelBuilder
from novoya_api.wishes.application.use_cases.answer_panel import AnswerPanel
from novoya_api.wishes.application.use_cases.closest_dates import GetClosestDates
from novoya_api.wishes.application.use_cases.get_panel_limits import GetPanelLimits
from novoya_api.wishes.application.use_cases.list_admin_wishes import ListAdminWishes
from novoya_api.wishes.application.use_cases.preferences import ListPreferences, RemovePreference
from novoya_api.wishes.application.use_cases.send_custom_request import SendCustomRequest
from novoya_api.wishes.application.use_cases.send_wish import SendWish
from novoya_api.wishes.infrastructure.answers_in_progress import InMemoryAnswersInProgress
from novoya_api.wishes.infrastructure.catalog import PartnerCatalog
from novoya_api.wishes.infrastructure.clients import AccountClients
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from novoya_api.wishes.infrastructure.llm.destination_reader import (
    LlmDestinationReader,
    NameMatchingReader,
)
from novoya_api.wishes.infrastructure.llm.panel_builder import (
    LlmPanelBuilder,
    TagsFromOffersBuilder,
)
from novoya_api.wishes.infrastructure.plan_statuses import PlanningPlanStatuses
from novoya_api.wishes.infrastructure.planner import PartnerPlanner

# One for the process: every request must see the answers the others are building.
ANSWERS_IN_PROGRESS = InMemoryAnswersInProgress()

# The client waits for both wish calls. A model slower than MODEL_TIMEOUT_SECONDS gives way
# to the next one, so a slow free model does not use the whole deadline.
DEADLINE_SECONDS = 20
MODEL_TIMEOUT_SECONDS = 8


def get_current_user_id(user: Annotated[CurrentUserView, Depends(require_client)]) -> UUID:
    """The signed-in client: 401 without a session, 403 for an agent (the admin passes)."""
    return user.user_id.value


# Built once: the counters must outlive the request (too_many_requests, 429).
@lru_cache
def get_rate_limiter() -> RateLimiter:
    return InMemoryRateLimiter(SystemClock())


def get_destination_reader() -> DestinationReader:
    try:
        # Short: the client waits for this answer, and name matching is the fallback. The
        # reader's deadline covers the answer and its retry.
        return LlmDestinationReader(_wish_orchestrator(), deadline_seconds=DEADLINE_SECONDS)
    except LLMError:
        return NameMatchingReader()  # no API key: the app still works


def get_panel_builder() -> PanelBuilder:
    try:
        return LlmPanelBuilder(_wish_orchestrator(), deadline_seconds=DEADLINE_SECONDS)
    except LLMError:
        return TagsFromOffersBuilder()  # no API key: the app still works


def _wish_orchestrator() -> Orchestrator:
    return get_orchestrator(
        deadline_seconds=DEADLINE_SECONDS, model_timeout_seconds=MODEL_TIMEOUT_SECONDS
    )


def get_send_wish(
    session: Annotated[AsyncSession, Depends(get_session)],
    reader: Annotated[DestinationReader, Depends(get_destination_reader)],
    panel_builder: Annotated[PanelBuilder, Depends(get_panel_builder)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> SendWish:
    return SendWish(
        wishes=SqlWishRepository(session),
        catalog=PartnerCatalog(session),
        reader=reader,
        panel_builder=panel_builder,
        rate_limiter=rate_limiter,
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
    )


def get_answer_panel(
    session: Annotated[AsyncSession, Depends(get_session)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> AnswerPanel:
    return AnswerPanel(
        wishes=SqlWishRepository(session),
        planner=PartnerPlanner(session),
        in_progress=ANSWERS_IN_PROGRESS,
        rate_limiter=rate_limiter,
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
    )


def get_send_custom_request(
    session: Annotated[AsyncSession, Depends(get_session)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> SendCustomRequest:
    return SendCustomRequest(
        wishes=SqlWishRepository(session),
        planner=PartnerPlanner(session),
        in_progress=ANSWERS_IN_PROGRESS,
        rate_limiter=rate_limiter,
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
    )


def get_closest_dates(
    session: Annotated[AsyncSession, Depends(get_session)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> GetClosestDates:
    return GetClosestDates(
        SqlWishRepository(session), PartnerCatalog(session), SystemClock(), rate_limiter
    )


def get_list_admin_wishes(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListAdminWishes:
    return ListAdminWishes(SqlWishRepository(session), AccountClients(session))


def get_list_preferences(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListPreferences:
    return ListPreferences(SqlWishRepository(session), PlanningPlanStatuses(session))


def get_remove_preference(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RemovePreference:
    return RemovePreference(
        SqlWishRepository(session),
        PlanningPlanStatuses(session),
        SqlAlchemyUnitOfWork(session),
        SystemClock(),
    )


def get_panel_limits(
    session: Annotated[AsyncSession, Depends(get_session)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> GetPanelLimits:
    return GetPanelLimits(
        SqlWishRepository(session), PartnerCatalog(session), SystemClock(), rate_limiter
    )
