from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.catalog.public import covered_destinations, limits_at, tags_at
from novoya_api.planning.public import trip_fits
from novoya_api.wishes.application.dto import PanelLimits
from novoya_api.wishes.domain.wish import Destination


class PartnerCatalog:
    """The partner catalog, read through catalog.public with the request's session, so a
    wish takes one connection from the pool, not one per catalog call."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def covered_destinations(self) -> list[Destination]:
        covered = await covered_destinations(session=self._session)
        return [Destination(country, city) for country, city in covered]

    async def tags_at(self, destination: Destination) -> list[str]:
        return await tags_at(destination.country, destination.city, session=self._session)

    async def limits(
        self, destination: Destination, today: date, persons: int | None = None
    ) -> PanelLimits | None:
        found = await limits_at(
            destination.country, destination.city, today, persons, session=self._session
        )
        if found is None:
            return None
        return PanelLimits(
            persons_min=found.persons_min,
            persons_max=found.persons_max,
            first_date=found.first_date,
            last_date=found.last_date,
            open_months=found.open_months,
        )

    async def fits(self, destination: Destination, persons: int, start: date, end: date) -> bool:
        return await trip_fits(
            destination.country, destination.city, persons, start, end, session=self._session
        )
