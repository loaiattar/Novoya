from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from novoya_api.planning.domain.plan import Plan, PlanStatus

QUEUE_PAGE = 50
QUEUE_CAP = 100


class ItemWrite(StrEnum):
    """What one PATCH writes on a plan item. Each value touches different columns."""

    PRICE = "price"
    REMOVE = "remove"
    RESTORE = "restore"


class PlanRepository(Protocol):
    async def add(self, plan: Plan) -> None: ...

    async def get(self, plan_id: UUID) -> Plan | None: ...

    async def list_queue(
        self,
        statuses: Sequence[PlanStatus],
        agent_id: UUID,
        *,
        limit: int = QUEUE_PAGE,
        offset: int = 0,
    ) -> list[Plan]:
        """Plans in these statuses, oldest updated first, without their items. Requested
        plans are everyone's; any other status lists only the plans assigned to agent_id."""
        ...

    async def save(self, plan: Plan) -> None:
        """Writes the plan row (status, assignee, timestamps). Not the items. When the plan
        leaves proposed, also its chosen extras (fixed from then on).

        Raises InvalidTransition if another request changed the status since get()."""
        ...

    async def save_item(self, plan: Plan, item_id: UUID, write: ItemWrite) -> None:
        """Writes only the columns for `write`, and the plan's updated_at.

        Price: negotiated_price, and only while the row is not removed (409 otherwise).
        Remove: removed=true and negotiated_price=NULL, after a last-item check.
        Restore: removed=false, leaving any price already in the database.

        Raises InvalidTransition if the status changed since get()."""
        ...

    async def save_extra(self, plan: Plan, extra_id: UUID) -> None:
        """Writes the price of one chosen extra, and the plan's updated_at.

        Raises InvalidTransition if the status changed since get()."""
        ...
