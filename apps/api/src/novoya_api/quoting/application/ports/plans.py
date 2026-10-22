from typing import Protocol
from uuid import UUID

from novoya_api.quoting.application.dto import QuotedPlan, QuoteTrip


class PlanQuoting(Protocol):
    async def quote(self, plan_id: UUID, agent_id: UUID) -> QuotedPlan:
        """Marks the plan quoted in the current transaction and returns its priced items.

        Raises when the plan is missing, not the agent's, not negotiating or not fully
        priced; nothing is written then."""
        ...

    async def trip(self, plan_id: UUID) -> QuoteTrip | None:
        """Where and when the plan's trip goes. None when the plan is gone."""
        ...

    async def priced(self, plan_id: UUID) -> QuotedPlan | None:
        """The quoted plan as its quote shows it, read only. None when it is gone."""
        ...

    async def record_answer(self, plan_id: UUID, accepted: bool) -> None:
        """Moves the plan to accepted or rejected in the current transaction."""
        ...
