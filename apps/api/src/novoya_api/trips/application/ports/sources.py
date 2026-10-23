from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from novoya_api.trips.application.dto import PlanSummary, WishSummary


class TripWishes(Protocol):
    async def of_user(self, user_id: UUID) -> list[WishSummary]:
        """This user's wishes, newest first."""
        ...


class TripPlans(Protocol):
    async def for_wishes(self, wish_ids: Sequence[UUID]) -> dict[UUID, PlanSummary]:
        """The plan of each of these wishes, keyed by wish id. Wishes without one are left out."""
        ...


class TripQuotes(Protocol):
    async def for_plans(self, plan_ids: Sequence[UUID]) -> dict[UUID, UUID]:
        """The id of the quote of each of these plans, keyed by plan id."""
        ...
