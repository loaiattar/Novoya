from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.messaging.domain.message import WishPlan
from novoya_api.planning.public import plans_of_wish


class PlanningPlans:
    """Plans through planning.public, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def of_wish(self, wish_id: UUID) -> list[WishPlan]:
        found = await plans_of_wish(wish_id, session=self._session)
        return [WishPlan(plan.status, plan.assigned_agent_id) for plan in found]
