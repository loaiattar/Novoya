from datetime import date
from typing import Protocol

from novoya_api.wishes.application.dto import DateOption, PanelLimits
from novoya_api.wishes.domain.wish import Destination


class Catalog(Protocol):
    """What wishes needs from the partner catalog."""

    async def covered_destinations(self) -> list[Destination]:
        """Destinations with at least one listed offer (active offer of an active partner)."""
        ...

    async def tags_at(self, destination: Destination) -> list[str]:
        """Tags ("section:tag") of the active offers there; the whole country without a city."""
        ...

    async def limits(
        self, destination: Destination, today: date, persons: int | None = None
    ) -> PanelLimits | None:
        """What the listed offers there can serve from today on, only those taking the group
        when persons is given; None when none is left."""
        ...

    async def fits(self, destination: Destination, persons: int, start: date, end: date) -> bool:
        """Whether a plan can be built for this trip there, whatever the model writes: the
        plan's own rule, so a yes never ends in no_offer_fits (#182, #183)."""
        ...

    async def closest_dates(
        self, destination: Destination, persons: int, start: date, end: date, earliest: date
    ) -> list[DateOption]:
        """The nearest dates before and after this trip, the same length and group, for which
        fits() would say yes, none before earliest (#184). Empty when none is near."""
        ...
