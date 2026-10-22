from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import count_users_by_role
from novoya_api.catalog.public import RowCounts as CatalogRowCounts
from novoya_api.catalog.public import count_catalog
from novoya_api.dashboard.application.dto import CatalogStats, RowCounts
from novoya_api.planning.public import count_plans_by_status
from novoya_api.quoting.public import count_quotes_by_status


class ModuleCounts:
    """Counts through each module's public.py, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def catalog(self) -> CatalogStats:
        found = await count_catalog(session=self._session)
        return CatalogStats(
            partners=_rows(found.partners),
            offers=_rows(found.offers),
            extras=_rows(found.extras),
            reviews_published=found.reviews_published,
            reviews_hidden=found.reviews_hidden,
        )

    async def users_by_role(self) -> dict[str, int]:
        return await count_users_by_role(session=self._session)

    async def plans_by_status(self) -> dict[str, int]:
        return await count_plans_by_status(session=self._session)

    async def quotes_by_status(self, now: datetime) -> dict[str, int]:
        return await count_quotes_by_status(now, session=self._session)


def _rows(counts: CatalogRowCounts) -> RowCounts:
    return RowCounts(counts.active, counts.hidden, counts.inactive)
