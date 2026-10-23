from dataclasses import replace
from datetime import date, timedelta

from novoya_api.planning.application.dto import OfferSummary, TripDates
from novoya_api.planning.application.ports.offer_catalog import OfferCatalog
from novoya_api.planning.application.use_cases.generate_plan import plannable

# How far from the asked dates other dates are looked for, each way.
SEARCH_DAYS = 90


class ClosestDates:
    """When no plan can be built for a trip, the nearest dates before and after it, the same
    length and for the same group, for which one can (#184), by the plan's own rule
    (plannable): choosing them never ends in no_offer_fits. No date before `earliest`.

    The catalog is read once, over the whole search: an offer's open days depend on the
    calendar only, so each shifted trip is worked out from that one read."""

    def __init__(self, catalog: OfferCatalog) -> None:
        self._catalog = catalog

    async def __call__(
        self,
        country: str,
        city: str | None,
        persons: int,
        start: date,
        end: date,
        earliest: date,
    ) -> list[TripDates]:
        trip_days = (end - start).days + 1
        first = max(earliest, start - timedelta(days=SEARCH_DAYS))
        last = start + timedelta(days=SEARCH_DAYS)
        if last < first:
            return []
        offers = await self._catalog.fitting_offers(
            country, city, (), persons, first, last + timedelta(days=trip_days - 1)
        )
        before = _nearest(offers, first, trip_days, start, step=-1, stop=first)
        after = _nearest(offers, first, trip_days, start, step=1, stop=last)
        return [found for found in (before, after) if found is not None]


def _nearest(
    offers: list[OfferSummary], first: date, trip_days: int, start: date, step: int, stop: date
) -> TripDates | None:
    """The first start from start + step towards stop (included) for which a plan can be
    built. open_days of `offers` count from `first`."""
    day = start + timedelta(days=step)
    while (day <= stop) if step > 0 else (day >= stop):
        fitting = _shifted(offers, (day - first).days, trip_days)
        if plannable(fitting, trip_days):
            return TripDates(day, day + timedelta(days=trip_days - 1), len(fitting))
        day += timedelta(days=step)
    return None


def _shifted(offers: list[OfferSummary], offset: int, trip_days: int) -> list[OfferSummary]:
    """The offers open on a trip starting `offset` days after the read's first day, with
    their open days counted from that trip's day 1. Offers closed all along are left out."""
    shifted: list[OfferSummary] = []
    for offer in offers:
        days = frozenset(
            day - offset for day in offer.open_days if offset < day <= offset + trip_days
        )
        if days:
            shifted.append(replace(offer, open_days=days))
    return shifted
