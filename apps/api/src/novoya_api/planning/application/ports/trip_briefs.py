from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from novoya_api.planning.application.dto import TripBrief


class TripBriefs(Protocol):
    """The wish text, place, dates, travellers and budget, for the agent's queue."""

    async def for_wish_ids(self, wish_ids: Sequence[UUID]) -> dict[UUID, TripBrief]: ...
