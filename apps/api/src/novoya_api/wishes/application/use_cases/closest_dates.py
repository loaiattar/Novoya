from datetime import date
from uuid import UUID

from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.wishes.application.dto import DateOption
from novoya_api.wishes.application.ports.catalog import Catalog
from novoya_api.wishes.application.ports.wish_repository import WishRepository
from novoya_api.wishes.application.use_cases.get_panel_limits import LIMITS_LIMIT, LIMITS_WINDOW
from novoya_api.wishes.domain.answers import check_trip_dates
from novoya_api.wishes.domain.errors import WishNotFound


class GetClosestDates:
    """When no offer fits the client's travellers and dates, the nearest dates before and
    after, the same length and group, that do (#184), from today on. Dates the answer would
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
        self, wish_id: UUID, user_id: UUID, persons: int, start: date, end: date
    ) -> list[DateOption]:
        await self._rate_limiter.hit(f"wishes:dates:{user_id}", LIMITS_LIMIT, LIMITS_WINDOW)
        wish = await self._wishes.get(wish_id)
        if wish is None or wish.user_id != user_id or wish.destination is None:
            raise WishNotFound("no such wish")
        today = self._clock.now().date()
        check_trip_dates(start, end, today)
        return await self._catalog.closest_dates(wish.destination, persons, start, end, today)
