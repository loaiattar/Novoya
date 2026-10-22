from typing import Protocol
from uuid import UUID

from novoya_api.quoting.application.dto import QuotedPlan


class PlanQuoting(Protocol):
    async def quote(self, plan_id: UUID, agent_id: UUID) -> QuotedPlan:
        """Marks the plan quoted in the current transaction and returns its priced items.

        Raises when the plan is missing, not the agent's, not negotiating or not fully
        priced; nothing is written then."""
        ...
