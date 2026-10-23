"""ClosestDates (#184) is tested with a fake catalog: offers open on given calendar days."""

from datetime import date, timedelta
from uuid import uuid4

from novoya_api.planning.application.dto import OfferSummary, TripDates
from novoya_api.planning.application.use_cases.closest_dates import SEARCH_DAYS, ClosestDates

START = date(2026, 6, 10)
END = date(2026, 6, 12)  # 3 days
TODAY = date(2026, 5, 1)


def offer(kind: str, open_on: set[date]) -> tuple[str, set[date]]:
    return kind, open_on


class FakeCatalog:
    """Answers fitting_offers like the catalog: each offer open on some calendar days, with
    its open days counted from the asked start."""

    def __init__(self, *offers: tuple[str, set[date]]) -> None:
        self.offers = [(uuid4(), kind, days) for kind, days in offers]
        self.calls: list[tuple[date, date, int]] = []

    async def fitting_offers(self, country, city, tags, persons, start, end):
        self.calls.append((start, end, persons))
        found = []
        for offer_id, kind, days in self.offers:
            open_days = frozenset((day - start).days + 1 for day in days if start <= day <= end)
            if open_days:
                found.append(OfferSummary(offer_id, kind, kind, "", (), False, open_days=open_days))
        return found


def days(first: date, count: int) -> set[date]:
    return {first + timedelta(days=offset) for offset in range(count)}


async def test_the_nearest_dates_before_and_after_with_how_many_offers_fit():
    # A hotel open every night of May and June but 5 to 19 June, and a walk open in July.
    hotel = days(date(2026, 5, 1), 61) - days(date(2026, 6, 5), 15)
    walk = days(date(2026, 7, 1), 31)
    catalog = FakeCatalog(offer("hotel", hotel), offer("activity", walk))

    found = await ClosestDates(catalog)("Greece", "Chania", 4, START, END, TODAY)

    # Before: the last start whose two nights (start, start + 1) are open is 3 June.
    # After: the first is 20 June. Only the hotel is open then.
    assert found == [
        TripDates(date(2026, 6, 3), date(2026, 6, 5), 1),
        TripDates(date(2026, 6, 20), date(2026, 6, 22), 1),
    ]
    # One read of the catalog, for the same group, over the whole search, from today on.
    [(first, last, persons)] = catalog.calls
    assert persons == 4
    assert first == TODAY  # later than START - SEARCH_DAYS
    assert last == START + timedelta(days=SEARCH_DAYS + 2)


async def test_no_date_before_the_earliest_day():
    walk = days(date(2026, 5, 1), 40)  # open until 9 June
    catalog = FakeCatalog(offer("activity", walk))

    found = await ClosestDates(catalog)("Greece", None, 2, START, END, START)

    assert found == []
    assert catalog.calls[0][0] == START


async def test_a_trip_with_one_open_activity_fits_without_a_hotel():
    walk = {date(2026, 6, 9)}
    found = await ClosestDates(FakeCatalog(offer("activity", walk)))(
        "Greece", None, 2, START, END, TODAY
    )

    # The plan's own rule: an activity on one day is a plan. 9 June is the nearest start.
    assert found == [TripDates(date(2026, 6, 9), date(2026, 6, 11), 1)]


async def test_only_after_when_nothing_fits_before():
    walk = {date(2026, 7, 1)}
    found = await ClosestDates(FakeCatalog(offer("activity", walk)))(
        "Greece", None, 2, START, END, TODAY
    )

    # The first 3-day trip that includes 1 July starts on 29 June.
    assert found == [TripDates(date(2026, 6, 29), date(2026, 7, 1), 1)]


async def test_a_hotel_alone_needs_every_night():
    # Open on single nights only: a 3-day trip needs two nights in a row.
    hotel = {date(2026, 6, 1), date(2026, 6, 3), date(2026, 6, 20), date(2026, 6, 21)}
    found = await ClosestDates(FakeCatalog(offer("hotel", hotel)))(
        "Greece", None, 2, START, END, TODAY
    )

    assert found == [TripDates(date(2026, 6, 20), date(2026, 6, 22), 1)]


async def test_nothing_within_the_search_gives_no_dates():
    far = {START + timedelta(days=SEARCH_DAYS + 30)}
    assert (
        await ClosestDates(FakeCatalog(offer("activity", far)))(
            "Greece", None, 2, START, END, TODAY
        )
        == []
    )
