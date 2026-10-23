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
- find_plan_ids(query, user_ids) -> the ids of the plans whose destination contains `query`
  or whose client is one of `user_ids`, for the admin search of quotes. At most SEARCH_CAP.
- count_plans_by_status() -> {status: count}: every status, 0 when no plan has it, for the
  admin dashboard. Counts only.
- plan_trips(plan_ids) -> {plan_id: TripBrief}: where and when each plan's trip goes; a plan
  whose wish is gone is left out.
- priced_plan(plan_id) -> PricedPlan | None: a quoted plan (answered or not) as its quote
  shows it, read only, for the client's quote page. None when it is gone or not quoted.
- mark_accepted(plan_id), mark_rejected(plan_id): the client's answer to the quote, in the
  caller's session (the caller commits, with the answer on its quote). Raises PlanNotFound
  (404) or InvalidTransition (409, not quoted, or changed meanwhile).
- plans_for_wishes(wish_ids) -> {wish id: WishPlan}: the plan id and status of each of these
  wishes, for the client's list of trips. Wishes without a plan are left out.
- plans_of_wish(wish_id) -> [WishPlanAccess]: the status and assigned agent of each plan of
  this wish, for the advisor chat's read rule (messaging). Empty when the wish has no plan.
- trip_fits(country, city, persons, start, end) -> whether a plan can be built for this trip
  whatever the model does: the rule the preference panel checks before sending (#183).
- plan_statuses(wish_ids) -> {wish_id: (status, ...)}: where the plans of these wishes stand,
  so wishes knows which answers the agency already works from (#165).
- delete_for_user(user_id): erases the plans of this user's wishes; their items and extras
  go with them. Erase the user's quotes first (quoting.public.delete_for_user) and the wishes
  after (wishes.public.delete_for_user): neither has a cascade. The caller commits.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
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
from novoya_api.planning.application.use_cases.generate_plan import GeneratePlan, plannable
from novoya_api.planning.application.use_cases.get_priced_plan import GetPricedPlan
from novoya_api.planning.application.use_cases.quote_plan import QuotePlan
from novoya_api.planning.application.use_cases.record_answer import RecordAnswer
from novoya_api.planning.domain.errors import NoOfferFits, PlanNotFound, PlanNotReady
from novoya_api.planning.domain.plan import PlanStatus
from novoya_api.planning.infrastructure.catalog import PartnerOffers
from novoya_api.planning.infrastructure.db.repository import SqlPlanRepository
from novoya_api.planning.infrastructure.llm.plan_writer import LlmPlanWriter, NoModelPlanWriter
from novoya_api.planning.infrastructure.llm.tools import TripBounds, travel_tools
from novoya_api.planning.infrastructure.wish_owners import WishOwners
from novoya_api.planning.infrastructure.wish_search import WishesSearch
from novoya_api.planning.infrastructure.wish_trips import WishTrips
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from novoya_api.shared.infrastructure.llm.client import get_orchestrator
from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.shared.infrastructure.llm.orchestrator import Tool
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
    "WishPlanAccess",
    "WishPlan",
    "count_plans_by_status",
    "delete_for_user",
    "find_plan_ids",
    "generate_plan",
    "mark_accepted",
    "mark_rejected",
    "plan_statuses",
    "trip_fits",
    "plan_trip",
    "plans_of_wish",
    "plan_trips",
    "plans_for_wishes",
    "priced_plan",
    "quote_plan",
]

# The plans a quote search may match, last changed first: past it the query is too broad, and
# the rest is dropped without a sign. Fine at the agency's size; a page would say "refine".
SEARCH_CAP = 1000

# A wish has one plan in practice; the cap only bounds the read.
WISH_PLANS_CAP = 20


@dataclass(frozen=True)
class WishPlanAccess:
    """Who works on a plan of a wish: its status (a PlanStatus value) and assigned agent."""

    status: str
    assigned_agent_id: UUID | None


# The client waits for the plan; the fallback covers a slow model.
DEADLINE_SECONDS = 60


@dataclass(frozen=True)
class WishPlan:
    """The plan built for a wish, as the client's list of trips shows it."""

    plan_id: UUID
    wish_id: UUID
    status: str  # the plan's status: proposed, requested, quoted, accepted...


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


async def priced_plan(plan_id: UUID, *, session: AsyncSession) -> PricedPlan | None:
    """A quoted plan as its quote shows it, read only. None when gone or not quoted."""
    use_case = GetPricedPlan(
        plans=SqlPlanRepository(session),
        catalog=PartnerOffers(session),
        trips=WishTrips(session),
        wishes=WishOwners(session),
    )
    return await use_case(plan_id)


async def mark_accepted(plan_id: UUID, *, session: AsyncSession) -> None:
    """The client accepted the quote: the plan becomes accepted in `session`. The caller
    commits."""
    await RecordAnswer(SqlPlanRepository(session), SystemClock())(plan_id, accepted=True)


async def mark_rejected(plan_id: UUID, *, session: AsyncSession) -> None:
    """The client rejected the quote: the plan becomes rejected in `session`. The caller
    commits."""
    await RecordAnswer(SqlPlanRepository(session), SystemClock())(plan_id, accepted=False)


async def count_plans_by_status(*, session: AsyncSession) -> dict[str, int]:
    """How many plans have each status. For admins only: the caller's router must require
    the admin role."""
    found = await SqlPlanRepository(session).count_by_status()
    return {status.value: found.get(status.value, 0) for status in PlanStatus}


async def find_plan_ids(
    query: str, user_ids: Sequence[UUID] = (), *, session: AsyncSession
) -> list[UUID]:
    """The plans whose destination contains `query`, or whose client is one of `user_ids`,
    newest first. The caller finds the users: accounts erases plans, so importing it here
    would loop. Stops at SEARCH_CAP without saying so: a search that broad needs refining.
    For admins only: the caller's router must require the admin role."""
    wish_ids = await WishesSearch(session).matching(query, user_ids)
    if not wish_ids:
        return []
    plans = await SqlPlanRepository(session).search([], wish_ids, limit=SEARCH_CAP)
    return [plan.id for plan in plans]


async def plan_trips(plan_ids: Sequence[UUID], *, session: AsyncSession) -> dict[UUID, TripBrief]:
    """Where and when each plan's trip goes, keyed by plan id. A plan whose wish is gone is
    left out."""
    plans = await SqlPlanRepository(session).list_by_ids(plan_ids)
    trips = await WishTrips(session).for_wish_ids([plan.wish_id for plan in plans])
    return {plan.id: trips[plan.wish_id] for plan in plans if plan.wish_id in trips}


async def plan_statuses(
    wish_ids: Sequence[UUID], *, session: AsyncSession
) -> dict[UUID, tuple[str, ...]]:
    """The status of each plan of these wishes, keyed by wish id. A wish without a plan is
    left out. The caller checks the wishes are the signed-in client's."""
    found = await SqlPlanRepository(session).statuses_by_wish(wish_ids)
    return {wish_id: tuple(statuses) for wish_id, statuses in found.items()}


def _writer() -> PlanWriter:
    try:
        orchestrator = get_orchestrator(deadline_seconds=DEADLINE_SECONDS)
    except LLMError:
        return NoModelPlanWriter()  # no API key: the plan is built from the catalog
    # No session: each tool call reads in a short session of its own, so no connection is held
    # while the model thinks between calls. The search is bound to the trip being planned
    # (#182): the model picks the place and the tags, never the dates or the travellers.
    return LlmPlanWriter(orchestrator, _trip_tools, DEADLINE_SECONDS)


def _trip_tools(request: PlanRequest) -> list[Tool]:
    trip = TripBounds(request.persons, request.start_date, request.end_date)
    return travel_tools(trip=trip)


async def delete_for_user(user_id: UUID, *, session: AsyncSession) -> None:
    """Erase the plans of this user's wishes, after their quotes. The caller commits."""
    wish_ids = await wish_ids_for_user(user_id, session=session)
    await SqlPlanRepository(session).delete_for_wishes(wish_ids)


async def plans_of_wish(wish_id: UUID, *, session: AsyncSession) -> list[WishPlanAccess]:
    """The status and assigned agent of each plan of this wish. Empty without a plan."""
    plans = await SqlPlanRepository(session).search([], [wish_id], limit=WISH_PLANS_CAP)
    return [WishPlanAccess(plan.status.value, plan.assigned_agent_id) for plan in plans]


async def plans_for_wishes(
    wish_ids: Sequence[UUID], *, session: AsyncSession
) -> dict[UUID, WishPlan]:
    """The plan of each of these wishes, keyed by wish id. Wishes without a plan are left out."""
    rows = await SqlPlanRepository(session).summaries_for_wishes(wish_ids)
    return {wish_id: WishPlan(plan_id, wish_id, status) for plan_id, wish_id, status in rows}


async def trip_fits(
    country: str,
    city: str | None,
    persons: int,
    start: date,
    end: date,
    *,
    session: AsyncSession,
) -> bool:
    """Whether generate_plan can build a plan for this trip whatever the model writes: the
    same fitting offers and fallback rule, so a "yes" never ends in no_offer_fits (#183)."""
    offers = await PartnerOffers(session).fitting_offers(country, city, (), persons, start, end)
    return plannable(offers, (end - start).days + 1)
