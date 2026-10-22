from datetime import datetime
from typing import Protocol

from novoya_api.dashboard.application.dto import CatalogStats


class Counts(Protocol):
    """Each module's counts, read in the request's session."""

    async def catalog(self) -> CatalogStats: ...

    async def users_by_role(self) -> dict[str, int]: ...

    async def plans_by_status(self) -> dict[str, int]: ...

    async def quotes_by_status(self, now: datetime) -> dict[str, int]:
        """As GET /quotes/{id} gives them at `now`: open, expired, accepted, rejected."""
        ...
