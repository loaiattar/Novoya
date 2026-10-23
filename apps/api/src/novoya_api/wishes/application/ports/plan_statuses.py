from collections.abc import Sequence
from typing import Protocol
from uuid import UUID


class PlanStatuses(Protocol):
    async def locked_wish_ids(self, wish_ids: Sequence[UUID]) -> set[UUID]:
        """The wishes among these with a plan requested, negotiating, quoted, accepted or
        rejected: the agency worked from their answers, so they stay. Only proposed plans
        do not lock."""
        ...
