import calendar
from datetime import date

from novoya_api.catalog.application.dto import LimitsView
from novoya_api.catalog.application.ports import OfferRepository
from novoya_api.catalog.domain import Offer


class DestinationLimits:
    """What the listed offers at a destination can serve from `today` on, for the preference
    panel (#183): the travellers stepper and the date fields offer only these. With persons,
    only the offers taking that group count. None when no such offer has an open day left."""

    def __init__(self, offers: OfferRepository) -> None:
        self._offers = offers

    async def __call__(
        self, country: str, city: str | None, today: date, persons: int | None = None
    ) -> LimitsView | None:
        seasons = [
            (offer, months)
            for offer, partner in await self._offers.list_at(country, city)
            if offer.is_listed_with(partner)
            and offer.available_to >= today
            and (persons is None or offer.fits_group(persons))
            and (months := _open_months(offer, today))
        ]
        if not seasons:
            return None
        return LimitsView(
            persons_min=min(offer.min_persons for offer, _ in seasons),
            persons_max=max(offer.max_persons for offer, _ in seasons),
            first_date=min(_first_open_day(offer, today) for offer, _ in seasons),
            last_date=max(_last_open_day(offer) for offer, _ in seasons),
            open_months=tuple(sorted(set().union(*(months for _, months in seasons)))),
        )


def _months(first: date, last: date) -> list[tuple[int, int]]:
    """(year, month) from first to last, at most twelve: the months repeat each year."""
    year, month = first.year, first.month
    found: list[tuple[int, int]] = []
    while len(found) < 12 and (year, month) <= (last.year, last.month):
        found.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return found


def _is_open(offer: Offer, month: int) -> bool:
    return not offer.opening_months or month in offer.opening_months


def _open_months(offer: Offer, today: date) -> set[int]:
    """The months with at least one day the offer is open, from today to its last day."""
    first = max(today, offer.available_from)
    return {month for _, month in _months(first, offer.available_to) if _is_open(offer, month)}


def _first_open_day(offer: Offer, today: date) -> date:
    """Its first open day from today on: the first open month's first day inside its window.
    Only called for an offer with an open month left."""
    first = max(today, offer.available_from)
    year, month = next((y, m) for y, m in _months(first, offer.available_to) if _is_open(offer, m))
    return max(first, date(year, month, 1))


def _last_open_day(offer: Offer) -> date:
    """Its last open day: the last open month's last day inside its window, looking back at
    most a year from its end."""
    last = offer.available_to
    year, month = last.year, last.month
    for _ in range(12):
        if _is_open(offer, month):
            return min(last, date(year, month, calendar.monthrange(year, month)[1]))
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return last
