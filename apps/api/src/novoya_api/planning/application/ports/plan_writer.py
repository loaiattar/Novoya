from dataclasses import dataclass
from typing import Protocol

from novoya_api.planning.application.dto import PlanRequest
from novoya_api.planning.domain.plan import DraftItem


@dataclass(frozen=True)
class DraftPlan:
    summary: str
    items: tuple[DraftItem, ...]


class PlanWriter(Protocol):
    async def write(self, request: PlanRequest) -> DraftPlan | None:
        """A draft plan, or None when the model could not write one."""
        ...
