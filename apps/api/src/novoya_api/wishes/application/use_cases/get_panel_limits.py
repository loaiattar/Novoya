from dataclasses import replace
from datetime import date, timedelta
from uuid import UUID

from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.wishes.application.dto import PanelLimits, PanelLimitsView
from novoya_api.wishes.application.ports.catalog import Catalog
from novoya_api.wishes.application.ports.wish_repository import WishRepository
from novoya_api.wishes.domain.answers import START_TOLERANCE, check_trip_dates
from novoya_api.wishes.domain.errors import WishNotFound

# The panel asks again on each change of travellers or dates: generous, but bounded.
LIMITS_LIMIT = 300
LIMITS_WINDOW = timedelta(minutes=10)
# The panel's travellers stop at 50, like the answer (AnswerPanelRequest.persons).
PANEL_MAX_PERSONS = 50


class GetPanelLimits:
    """What the panel of the client's wish may offer, read from the catalog each time, so an
    offer added in the back office shows at once (#183). With the travellers and both dates,
    also whether a plan can be built for them, by the plan's own rule; dates the answer would
    refuse are refused here too (InvalidAnswers). Someone else's wish, or one with no
    destination yet, looks like not found."""

    def __init__(
        self, wishes: WishRepository, catalog: Catalog, clock: Clock, rate_limiter: RateLimiter
    ) -> None:
        self._wishes = wishes
        self._catalog = catalog
        self._clock = clock
        self._rate_limiter = rate_limiter

    async def __call__(
        self,
        wish_id: UUID,
        user_id: UUID,
        persons: int | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> PanelLimitsView:
        await self._rate_limiter.hit(f"wishes:limits:{user_id}", LIMITS_LIMIT, LIMITS_WINDOW)
        wish = await self._wishes.get(wish_id)
        if wish is None or wish.user_id != user_id or wish.destination is None:
            raise WishNotFound("no such wish")
        today = self._clock.now().date()
        # From the day before: the server's day is UTC, and that can still be today for the
        # client (START_TOLERANCE, as for the answer).
        from_day = today - START_TOLERANCE
        if persons is None or start is None or end is None:
            limits = await self._catalog.limits(wish.destination, from_day)
            return PanelLimitsView(limits=_within_panel(limits), fits=None)
        check_trip_dates(start, end, today)
        limits = await self._catalog.limits(wish.destination, from_day, persons)
        fits = await self._catalog.fits(wish.destination, persons, start, end)
        return PanelLimitsView(limits=_within_panel(limits), fits=fits)


def _within_panel(limits: PanelLimits | None) -> PanelLimits | None:
    """The group sizes the panel can offer: at most PANEL_MAX_PERSONS. None when every offer
    there needs a bigger group."""
    if limits is None or limits.persons_min > PANEL_MAX_PERSONS:
        return None
    return replace(limits, persons_max=min(limits.persons_max, PANEL_MAX_PERSONS))
