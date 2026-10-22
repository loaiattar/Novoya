from uuid import UUID

from novoya_api.planning.application.ports.plan_repository import PlanRepository
from novoya_api.planning.domain.errors import PlanNotFound
from novoya_api.shared.application.clock import Clock


class RecordAnswer:
    """The client accepted or rejected the plan's quote. Called by quoting, which saves the
    answer on the quote in the same session. No commit here: both are written together."""

    def __init__(self, plans: PlanRepository, clock: Clock) -> None:
        self._plans = plans
        self._clock = clock

    async def __call__(self, plan_id: UUID, accepted: bool) -> None:
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFound("no such plan")
        plan.record_answer(accepted, self._clock.now())
        await self._plans.save(plan)
