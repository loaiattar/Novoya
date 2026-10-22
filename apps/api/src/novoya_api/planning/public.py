"""What other modules may use from planning. Nothing else in planning may be imported.

- generate_plan(request) -> PlanView: builds the proposed plan of an answered wish and adds
  it to the caller's session; the caller commits. It ends the session's read transaction
  before the model runs, so call it before writing anything in that session. Raises
  NoOfferFits (422) when no listed offer fits the travellers and dates.
- quote_plan(plan_id, agent_id) -> PricedPlan: the assigned agent sends the quote. The plan
  becomes quoted in the caller's session (the caller commits, with its quote) and its priced
  items come back, never with a partner name. Raises PlanNotFound (404), PermissionDenied
  (403, another agent), InvalidTransition (409, not negotiating) or PlanNotReady (422).
- plan_trip(plan_id) -> TripBrief | None: the wish behind the plan (place, dates,
  travellers), for the quote email. None when the plan or its wish is gone.
- plan_status(plan_id) -> str | None: the plan's status (`quoted`, `accepted`, ...), so
  quoting can show the client's answer. None when the plan is gone.
- delete_for_user(user_id): erases the plans of this user's wishes; their items and extras
  go with them. Erase the user's quotes first (quoting.public.delete_for_user) and the wishes
  after (wishes.public.delete_for_user): neither has a cascade. The caller commits.

Planned:
- mark_accepted(plan_id), mark_rejected(plan_id) (called by quoting)
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.planning.application.dto import (
    PlanItemView,
    PlanRequest,
    PlanView,
    PricedExtra,
    PricedItem,
    PricedPlan,
    TripBrief,
)
from novoya_api.planning.application.ports.plan_writer import PlanWriter
from novoya_api.planning.application.use_cases.generate_plan import GeneratePlan
from novoya_api.planning.application.use_cases.quote_plan import QuotePlan
from novoya_api.planning.domain.errors import NoOfferFits, PlanNotFound, PlanNotReady
from novoya_api.planning.infrastructure.catalog import PartnerOffers
from novoya_api.planning.infrastructure.db.repository import SqlPlanRepository
from novoya_api.planning.infrastructure.llm.plan_writer import LlmPlanWriter, NoModelPlanWriter
from novoya_api.planning.infrastructure.llm.tools import travel_tools
from novoya_api.planning.infrastructure.wish_owners import WishOwners
from novoya_api.planning.infrastructure.wish_trips import WishTrips
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from novoya_api.shared.infrastructure.llm.client import get_orchestrator
from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.shared.infrastructure.system_clock import SystemClock
from novoya_api.wishes.public import ids_for_user as wish_ids_for_user

__all__ = [
    "NoOfferFits",
    "PlanItemView",
    "PlanNotFound",
    "PlanNotReady",
    "PlanRequest",
    "PlanView",
    "PricedExtra",
    "PricedItem",
    "PricedPlan",
    "TripBrief",
    "delete_for_user",
    "generate_plan",
    "plan_status",
    "plan_trip",
    "quote_plan",
]

# The client waits for the plan; the fallback covers a slow model.
DEADLINE_SECONDS = 60


async def generate_plan(request: PlanRequest, *, session: AsyncSession) -> PlanView:
    """The proposed plan of an answered wish, added to `session`. The caller commits."""
    use_case = GeneratePlan(
        catalog=PartnerOffers(session),
        writer=_writer(),
        plans=SqlPlanRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
        clock=SystemClock(),
    )
    return await use_case(request)


async def quote_plan(plan_id: UUID, agent_id: UUID, *, session: AsyncSession) -> PricedPlan:
    """The plan marked quoted in `session`, with its prices. The caller commits."""
    use_case = QuotePlan(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        trips=WishTrips(session),
        wishes=WishOwners(session),
        clock=SystemClock(),
    )
    return await use_case(plan_id, agent_id)


async def plan_trip(plan_id: UUID, *, session: AsyncSession) -> TripBrief | None:
    """The wish behind the plan: where, when, how many. None when either is gone."""
    plan = await SqlPlanRepository(session).get(plan_id)
    if plan is None:
        return None
    return (await WishTrips(session).for_wish_ids([plan.wish_id])).get(plan.wish_id)


async def plan_status(plan_id: UUID, *, session: AsyncSession) -> str | None:
    """The plan's status, without loading its items. None when the plan is gone."""
    status = await SqlPlanRepository(session).status_of(plan_id)
    return None if status is None else status.value


def _writer() -> PlanWriter:
    try:
        orchestrator = get_orchestrator(deadline_seconds=DEADLINE_SECONDS)
    except LLMError:
        return NoModelPlanWriter()  # no API key: the plan is built from the catalog
    # No session: each tool call reads in a short session of its own, so no connection is held
    # while the model thinks between calls.
    return LlmPlanWriter(orchestrator, travel_tools(), DEADLINE_SECONDS)


async def delete_for_user(user_id: UUID, *, session: AsyncSession) -> None:
    """Erase the plans of this user's wishes, after their quotes. The caller commits."""
    wish_ids = await wish_ids_for_user(user_id, session=session)
    await SqlPlanRepository(session).delete_for_wishes(wish_ids)
