from novoya_api.dashboard.application.dto import AdminStats
from novoya_api.dashboard.application.ports import Counts
from novoya_api.shared.application.clock import Clock


class GetAdminStats:
    """The agency at a glance: the catalog, the accounts by role, the plans and the quotes
    by status."""

    def __init__(self, counts: Counts, clock: Clock) -> None:
        self._counts = counts
        self._clock = clock

    async def __call__(self) -> AdminStats:
        # One session runs one query at a time: the counts are read one after the other.
        return AdminStats(
            catalog=await self._counts.catalog(),
            users=await self._counts.users_by_role(),
            plans=await self._counts.plans_by_status(),
            quotes=await self._counts.quotes_by_status(self._clock.now()),
        )
