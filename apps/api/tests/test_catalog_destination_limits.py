"""DestinationLimits with a fake repository: what the preference panel may offer (#183)."""

from datetime import date

from novoya_api.catalog.application.dto import LimitsView
from novoya_api.catalog.application.use_cases.destination_limits import DestinationLimits
from tests.test_catalog_public import FakeOffers, _offer, _partner

# The default test offer is available from 2026-04-01 to 2026-10-31.
TODAY = date(2026, 5, 15)


async def limits(pairs, country="Portugal", city="Lisbon", today=TODAY):
    return await DestinationLimits(FakeOffers(pairs))(country, city, today)


async def test_persons_go_from_the_smallest_minimum_to_the_largest_maximum():
    hotel = _partner()
    pairs = [
        (_offer(hotel, min_persons=2, max_persons=4), hotel),
        (_offer(hotel, min_persons=1, max_persons=2), hotel),
        (_offer(hotel, min_persons=3, max_persons=8), hotel),
    ]

    found = await limits(pairs)

    assert found is not None
    assert (found.persons_min, found.persons_max) == (1, 8)


async def test_first_date_is_never_before_today():
    hotel = _partner()

    found = await limits([(_offer(hotel), hotel)])

    assert found is not None
    assert found.first_date == TODAY


async def test_first_date_is_the_earliest_availability_when_it_is_in_the_future():
    hotel = _partner()
    pairs = [
        (_offer(hotel, available_from=date(2026, 7, 1)), hotel),
        (_offer(hotel, available_from=date(2026, 6, 10)), hotel),
    ]

    found = await limits(pairs)

    assert found is not None
    assert found.first_date == date(2026, 6, 10)


async def test_last_date_is_the_latest_availability():
    hotel = _partner()
    pairs = [
        (_offer(hotel, available_to=date(2026, 8, 31)), hotel),
        (_offer(hotel, available_to=date(2026, 12, 15)), hotel),
    ]

    found = await limits(pairs)

    assert found is not None
    assert found.last_date == date(2026, 12, 15)


async def test_open_months_come_from_the_offers_opening_months_sorted():
    hotel = _partner()
    pairs = [
        (_offer(hotel, opening_months=(9,)), hotel),
        (_offer(hotel, opening_months=(7, 6)), hotel),
    ]

    found = await limits(pairs)

    assert found is not None
    assert found.open_months == (6, 7, 9)


async def test_an_offer_without_opening_months_opens_every_month_of_its_window_from_today():
    hotel = _partner()

    found = await limits([(_offer(hotel), hotel)])

    assert found is not None
    assert found.open_months == (5, 6, 7, 8, 9, 10)


async def test_open_months_outside_the_offers_window_are_left_out():
    hotel = _partner()
    winter_and_june = _offer(hotel, opening_months=(1, 2, 6, 11, 12))

    found = await limits([(winter_and_june, hotel)])

    assert found is not None
    assert found.open_months == (6,)


async def test_open_months_before_today_are_left_out():
    hotel = _partner()
    spring = _offer(hotel, opening_months=(4, 5, 6))

    found = await limits([(spring, hotel)], today=date(2026, 6, 2))

    assert found is not None
    assert found.open_months == (6,)


async def test_the_limits_are_a_limits_view():
    hotel = _partner()
    stay = _offer(
        hotel,
        min_persons=2,
        max_persons=4,
        available_from=date(2026, 6, 1),
        available_to=date(2026, 8, 31),
    )

    found = await limits([(stay, hotel)])

    assert found == LimitsView(
        persons_min=2,
        persons_max=4,
        first_date=date(2026, 6, 1),
        last_date=date(2026, 8, 31),
        open_months=(6, 7, 8),
    )


async def test_inactive_and_hidden_offers_and_partners_are_ignored():
    hotel = _partner()
    closed = _partner(active=False)
    hidden_partner = _partner(hidden=True)
    listed = _offer(hotel, min_persons=2, max_persons=4, available_to=date(2026, 8, 31))
    unlisted = {
        "min_persons": 1,
        "max_persons": 20,
        "available_from": date(2026, 4, 1),
        "available_to": date(2026, 12, 31),
    }
    pairs = [
        (listed, hotel),
        (_offer(hotel, active=False, **unlisted), hotel),
        (_offer(hotel, hidden=True, **unlisted), hotel),
        (_offer(closed, **unlisted), closed),
        (_offer(hidden_partner, **unlisted), hidden_partner),
    ]

    found = await limits(pairs)

    assert found is not None
    assert (found.persons_min, found.persons_max) == (2, 4)
    assert found.last_date == date(2026, 8, 31)
    assert found.open_months == (5, 6, 7, 8)


async def test_offers_that_ended_before_today_are_ignored():
    hotel = _partner()
    ended = _offer(
        hotel,
        min_persons=1,
        max_persons=20,
        available_from=date(2026, 4, 1),
        available_to=date(2026, 5, 14),
    )
    current = _offer(hotel, min_persons=2, max_persons=4)

    found = await limits([(ended, hotel), (current, hotel)])

    assert found is not None
    assert (found.persons_min, found.persons_max) == (2, 4)


async def test_without_a_city_the_whole_country_counts():
    lisbon = _partner(country="Portugal", city="Lisbon")
    porto = _partner(country="Portugal", city="Porto")
    madrid = _partner(country="Spain", city="Madrid")
    pairs = [
        (_offer(lisbon, min_persons=2, max_persons=4), lisbon),
        (_offer(porto, min_persons=1, max_persons=6), porto),
        (_offer(madrid, min_persons=1, max_persons=30), madrid),
    ]

    in_lisbon = await limits(pairs, city="Lisbon")
    in_portugal = await limits(pairs, city=None)

    assert in_lisbon is not None and in_portugal is not None
    assert (in_lisbon.persons_min, in_lisbon.persons_max) == (2, 4)
    assert (in_portugal.persons_min, in_portugal.persons_max) == (1, 6)


async def test_no_listed_offer_at_the_destination_means_no_limits():
    hotel = _partner()
    closed = _partner(active=False)
    pairs = [(_offer(hotel, hidden=True), hotel), (_offer(closed), closed)]

    assert await limits(pairs) is None
    assert await limits([]) is None


async def test_only_offers_that_ended_before_today_means_no_limits():
    hotel = _partner()
    ended = _offer(hotel, available_to=date(2026, 5, 14))

    assert await limits([(ended, hotel)]) is None


async def test_an_offer_ending_today_still_counts():
    hotel = _partner()
    last_day = _offer(hotel, available_to=TODAY)

    found = await limits([(last_day, hotel)])

    assert found is not None
    assert (found.first_date, found.last_date) == (TODAY, TODAY)
    assert found.open_months == (5,)


# The dates the offers are really open, and the group asked for (review of #183)


async def test_first_and_last_dates_are_the_first_and_last_open_days():
    # Available for two years but open only in summer: the panel must not offer October.
    hotel = _partner()
    summer = _offer(
        hotel,
        available_from=date(2026, 1, 1),
        available_to=date(2027, 12, 31),
        opening_months=(6, 7, 8),
    )

    found = await limits([(summer, hotel)], today=date(2026, 10, 23))

    assert found is not None
    assert (found.first_date, found.last_date) == (date(2027, 6, 1), date(2027, 8, 31))


async def test_an_offer_with_no_open_day_left_in_its_window_is_ignored():
    hotel = _partner()
    june_only = _offer(
        hotel,
        available_from=date(2026, 1, 1),
        available_to=date(2026, 3, 31),
        opening_months=(6,),
    )

    assert await limits([(june_only, hotel)], today=date(2026, 1, 10)) is None


async def test_with_a_group_only_the_offers_taking_it_count():
    hotel = _partner()
    small = _offer(hotel, min_persons=1, max_persons=4, opening_months=(6,))
    large = _offer(hotel, min_persons=8, max_persons=12, opening_months=(8,))

    found = await DestinationLimits(FakeOffers([(small, hotel), (large, hotel)]))(
        "Portugal", "Lisbon", TODAY, persons=6
    )
    assert found is None

    found = await DestinationLimits(FakeOffers([(small, hotel), (large, hotel)]))(
        "Portugal", "Lisbon", TODAY, persons=10
    )
    assert found is not None
    assert found.open_months == (8,)
