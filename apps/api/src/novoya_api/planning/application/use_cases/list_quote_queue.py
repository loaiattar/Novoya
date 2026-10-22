from collections.abc import Sequence
from uuid import UUID

from novoya_api.planning.application.agent_view import queue_entry_as_view
from novoya_api.planning.application.dto import QueueEntryView
from novoya_api.planning.application.ports.plan_repository import (
    QUEUE_CAP,
    QUEUE_PAGE,
    PlanRepository,
)
from novoya_api.planning.application.ports.trip_briefs import TripBriefs
from novoya_api.planning.domain.plan import PlanStatus


class ListQuoteQueue:
    """The agent's queue, oldest first, with the wish the client sent: the requested plans
    everyone can take, and the agent's own plans in the other statuses asked for."""

    def __init__(self, plans: PlanRepository, trips: TripBriefs) -> None:
        self._plans = plans
        self._trips = trips

    async def __call__(
        self,
        agent_id: UUID,
        statuses: Sequence[PlanStatus] = (PlanStatus.REQUESTED,),
        *,
        limit: int = QUEUE_PAGE,
        offset: int = 0,
    ) -> list[QueueEntryView]:
        waiting = await self._plans.list_queue(
            statuses, agent_id, limit=min(max(limit, 1), QUEUE_CAP), offset=max(offset, 0)
        )
        trips = await self._trips.for_wish_ids([plan.wish_id for plan in waiting])
        return [queue_entry_as_view(plan, trips.get(plan.wish_id)) for plan in waiting]
