from typing import Protocol
from uuid import UUID

from novoya_api.quoting.application.dto import QuotedPlan, QuoteTrip
from novoya_api.quoting.domain.quote import QuoteStatus


class PlanQuoting(Protocol):
    async def quote(self, plan_id: UUID, agent_id: UUID) -> QuotedPlan:
        """Marks the plan quoted in the current transaction and returns its priced items.

        Raises when the plan is missing, not the agent's, not negotiating or not fully
        priced; nothing is written then."""
        ...

    async def trip(self, plan_id: UUID) -> QuoteTrip | None:
        """Where and when the plan's trip goes. None when the plan is gone."""
        ...

    async def answer(self, plan_id: UUID) -> QuoteStatus | None:
        """The client's answer, kept on the plan: ACCEPTED or REJECTED. None before an
        answer, or when the plan is gone."""
        ...
