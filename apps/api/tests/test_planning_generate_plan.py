"""GeneratePlan is tested with fake ports: a scripted catalog, writer and repository."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from novoya_api.planning.application.dto import OfferSummary, PlanRequest
from novoya_api.planning.application.ports.plan_writer import DraftPlan
from novoya_api.planning.application.use_cases.generate_plan import GeneratePlan
from novoya_api.planning.domain.errors import NoOfferFits
from novoya_api.planning.domain.plan import DraftItem, Plan, PlanStatus

WISH_ID = UUID("00000000-0000-0000-0000-0000000000a1")
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
EVERY_DAY = frozenset(range(1, 32))  # open on every day of any trip these tests plan

HOTEL = OfferSummary(
    UUID("00000000-0000-0000-0000-0000000000b1"),
    "hotel",
    "Sea view hotel",
    "Rooms over the bay",
    ("style:beach",),
    False,
    open_days=EVERY_DAY,
)
WALK = OfferSummary(
    UUID("00000000-0000-0000-0000-0000000000b2"),
    "guide",
    "Old town walk",
    "Two hours with a local guide",
    ("style:city",),
    False,
    open_days=EVERY_DAY,
)
BOAT = OfferSummary(
    UUID("00000000-0000-0000-0000-0000000000b3"),
    "activity",
    "Boat trip",
    "A day at sea",
    ("style:beach",),
    True,
    open_days=EVERY_DAY,
)
TRANSFER = OfferSummary(
    UUID("00000000-0000-0000-0000-0000000000b4"),
    "transport",
    "Airport transfer",
    "Car from the airport",
    (),
    False,
    open_days=EVERY_DAY,
)
UNKNOWN = UUID("00000000-0000-0000-0000-0000000000ff")


def plan_request(tags: tuple[str, ...] = ("style:beach",), days: int = 8) -> PlanRequest:
    return PlanRequest(
        wish_id=WISH_ID,
        text="A week by the sea in Chania",
        country="Greece",
        city="Chania",
        tags=tags,
        persons=2,
        start_date=date(2026, 5, 10),
        end_date=date(2026, 5, 10 + days - 1),
        budget_max=Decimal("1500"),
    )


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeCatalog:
    """Every fitting offer without tags; the `ranked` offers when tags are given."""

    def __init__(self, fitting: list[OfferSummary], ranked: list[OfferSummary] | None = None):
        self.fitting = fitting
        self.ranked = fitting if ranked is None else ranked
        self.calls: list[dict] = []

    async def fitting_offers(self, country, city, tags, persons, start, end):
        self.calls.append(
            {
                "country": country,
                "city": city,
                "tags": tuple(tags),
                "persons": persons,
                "start": start,
                "end": end,
            }
        )
        return list(self.ranked if tags else self.fitting)


class FakeUnitOfWork:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def commit(self) -> None:
        self.events.append("commit")

    async def rollback(self) -> None:
        self.events.append("rollback")


class FakeWriter:
    def __init__(self, draft: DraftPlan | None) -> None:
        self.draft = draft
        self.requests: list[PlanRequest] = []
        self.events: list[str] = []

    async def write(self, request: PlanRequest) -> DraftPlan | None:
        self.requests.append(request)
        self.events.append("write")
        return self.draft


class FakePlans:
    def __init__(self) -> None:
        self.added: list[Plan] = []

    async def add(self, plan: Plan) -> None:
        self.added.append(plan)

    async def get(self, plan_id: UUID) -> Plan | None:
        return next((plan for plan in self.added if plan.id == plan_id), None)


class Setup:
    def __init__(self, catalog: FakeCatalog, draft: DraftPlan | None) -> None:
        self.catalog = catalog
        self.writer = FakeWriter(draft)
        self.events = self.writer.events
        self.plans = FakePlans()
        self.generate = GeneratePlan(
            catalog=catalog,
            writer=self.writer,
            plans=self.plans,
            uow=FakeUnitOfWork(self.events),
            clock=FixedClock(),
        )


def draft(*items: DraftItem, summary: str = "Sun, sea and the old town") -> DraftPlan:
    return DraftPlan(summary=summary, items=items)


ALL = [HOTEL, WALK, BOAT, TRANSFER]


# The model's plan


async def test_a_valid_draft_is_stored_and_returned_with_offer_details():
    setup = Setup(
        FakeCatalog(ALL),
        draft(DraftItem(HOTEL.id, 1, 7, None), DraftItem(WALK.id, 2, 1, "In the morning")),
    )

    view = await setup.generate(plan_request())

    assert len(setup.plans.added) == 1
    plan = setup.plans.added[0]
    assert plan.status is PlanStatus.PROPOSED
    assert plan.wish_id == WISH_ID
    assert plan.summary == "Sun, sea and the old town"
    assert plan.created_at == NOW
    assert view.id == plan.id
    assert view.wish_id == WISH_ID
    assert view.status == "proposed"
    assert view.summary == "Sun, sea and the old town"
    assert [
        (i.offer_id, i.day, i.quantity, i.note, i.kind, i.title, i.description) for i in view.items
    ] == [
        (HOTEL.id, 1, 7, None, "hotel", "Sea view hotel", "Rooms over the bay"),
        (WALK.id, 2, 1, "In the morning", "guide", "Old town walk", "Two hours with a local guide"),
    ]
    assert [i.id for i in view.items] == [i.id for i in plan.items]


async def test_the_catalog_is_asked_for_every_offer_fitting_the_trip_without_tags():
    catalog = FakeCatalog(ALL)
    setup = Setup(catalog, draft(DraftItem(HOTEL.id, 1, 7, None)))

    await setup.generate(plan_request())

    assert catalog.calls[0] == {
        "country": "Greece",
        "city": "Chania",
        "tags": (),
        "persons": 2,
        "start": date(2026, 5, 10),
        "end": date(2026, 5, 17),
    }


async def test_the_writer_gets_the_request():
    setup = Setup(FakeCatalog(ALL), draft(DraftItem(HOTEL.id, 1, 7, None)))
    request = plan_request()

    await setup.generate(request)

    assert setup.writer.requests == [request]


async def test_an_unknown_or_inactive_offer_is_dropped_before_saving():
    setup = Setup(
        FakeCatalog(ALL),
        draft(DraftItem(UNKNOWN, 1, 1, None), DraftItem(WALK.id, 2, 1, None)),
    )

    view = await setup.generate(plan_request())

    assert [item.offer_id for item in setup.plans.added[0].items] == [WALK.id]
    assert [item.offer_id for item in view.items] == [WALK.id]


async def test_an_offer_that_does_not_fit_the_travellers_or_dates_is_dropped():
    # BOAT exists in the catalog but is not returned as fitting (too few places, wrong dates).
    setup = Setup(
        FakeCatalog([HOTEL, WALK]),
        draft(DraftItem(BOAT.id, 3, 1, None), DraftItem(HOTEL.id, 1, 7, None)),
    )

    await setup.generate(plan_request())

    assert [item.offer_id for item in setup.plans.added[0].items] == [HOTEL.id]


async def test_an_item_on_a_day_outside_the_trip_is_dropped():
    setup = Setup(
        FakeCatalog(ALL),
        draft(DraftItem(WALK.id, 9, 1, None), DraftItem(HOTEL.id, 1, 7, None)),
    )

    await setup.generate(plan_request(days=8))

    assert [item.offer_id for item in setup.plans.added[0].items] == [HOTEL.id]


async def test_without_tags_the_plan_is_not_based_on_preferences():
    setup = Setup(FakeCatalog(ALL), draft(DraftItem(HOTEL.id, 1, 7, None)))

    view = await setup.generate(plan_request(tags=()))

    assert view.based_on_preferences is False
    assert setup.plans.added[0].based_on_preferences is False


async def test_with_tags_the_plan_is_based_on_preferences():
    setup = Setup(FakeCatalog(ALL), draft(DraftItem(HOTEL.id, 1, 7, None)))

    view = await setup.generate(plan_request(tags=("style:beach",)))

    assert view.based_on_preferences is True
    assert setup.plans.added[0].based_on_preferences is True


async def test_no_item_ever_has_a_negotiated_price():
    setup = Setup(
        FakeCatalog(ALL),
        draft(DraftItem(HOTEL.id, 1, 7, None), DraftItem(WALK.id, 2, 1, None)),
    )

    await setup.generate(plan_request())

    assert all(item.negotiated_price is None for item in setup.plans.added[0].items)


# Fallback when the model gives no usable plan


async def test_without_a_draft_the_fallback_puts_the_hotel_on_day_one_for_every_night():
    setup = Setup(FakeCatalog([WALK, HOTEL, BOAT]), None)

    view = await setup.generate(plan_request(tags=(), days=8))

    hotel = view.items[0]
    assert (hotel.offer_id, hotel.day, hotel.quantity, hotel.kind) == (HOTEL.id, 1, 7, "hotel")
    assert view.summary
    assert setup.plans.added[0].summary == view.summary


async def test_the_fallback_hotel_has_at_least_one_night_for_a_one_day_trip():
    setup = Setup(FakeCatalog([HOTEL, WALK]), None)

    view = await setup.generate(plan_request(tags=(), days=1))

    hotel = next(item for item in view.items if item.offer_id == HOTEL.id)
    assert (hotel.day, hotel.quantity) == (1, 1)


async def test_the_fallback_puts_other_offers_one_per_day_in_rank_order():
    # The catalog ranks the featured boat first.
    setup = Setup(FakeCatalog([BOAT, HOTEL, WALK, TRANSFER]), None)

    view = await setup.generate(plan_request(tags=(), days=8))

    others = [(i.offer_id, i.day, i.quantity, i.note) for i in view.items if i.offer_id != HOTEL.id]
    assert others == [(BOAT.id, 1, 1, None), (WALK.id, 2, 1, None), (TRANSFER.id, 3, 1, None)]


async def test_the_fallback_puts_the_featured_offer_first_after_the_hotel():
    setup = Setup(FakeCatalog([BOAT, WALK, HOTEL]), None)

    view = await setup.generate(plan_request(tags=(), days=8))

    assert [item.offer_id for item in view.items][:2] == [HOTEL.id, BOAT.id]


async def test_the_fallback_has_at_most_one_offer_per_day_of_the_trip():
    setup = Setup(FakeCatalog([BOAT, WALK, TRANSFER]), None)

    view = await setup.generate(plan_request(tags=(), days=2))

    assert [(item.offer_id, item.day) for item in view.items] == [(BOAT.id, 1), (WALK.id, 2)]


async def test_the_fallback_uses_the_offers_ranked_by_the_tags():
    catalog = FakeCatalog(fitting=[WALK, TRANSFER, BOAT, HOTEL], ranked=[BOAT, HOTEL])
    setup = Setup(catalog, None)

    view = await setup.generate(plan_request(tags=("style:beach",)))

    assert [item.offer_id for item in view.items] == [HOTEL.id, BOAT.id]
    assert catalog.calls[-1]["tags"] == ("style:beach",)


async def test_the_fallback_uses_every_fitting_offer_when_no_offer_matches_the_tags():
    catalog = FakeCatalog(fitting=[WALK, HOTEL], ranked=[])
    setup = Setup(catalog, None)

    view = await setup.generate(plan_request(tags=("style:nightlife",)))

    assert [item.offer_id for item in view.items] == [HOTEL.id, WALK.id]


async def test_a_draft_whose_items_are_all_invalid_falls_back():
    setup = Setup(
        FakeCatalog([BOAT, HOTEL]),
        draft(DraftItem(UNKNOWN, 1, 1, None), DraftItem(BOAT.id, 0, 1, None), summary="Bad"),
    )

    view = await setup.generate(plan_request(tags=(), days=8))

    assert [(i.offer_id, i.day) for i in view.items] == [(HOTEL.id, 1), (BOAT.id, 1)]
    assert view.summary != "Bad"
    assert len(setup.plans.added) == 1


async def test_the_fallback_never_has_a_negotiated_price():
    setup = Setup(FakeCatalog(ALL), None)

    await setup.generate(plan_request())

    assert all(item.negotiated_price is None for item in setup.plans.added[0].items)


# No offer fits


async def test_without_any_fitting_offer_raises_no_offer_fits_and_stores_nothing():
    setup = Setup(FakeCatalog([]), draft(DraftItem(HOTEL.id, 1, 7, None)))

    with pytest.raises(NoOfferFits):
        await setup.generate(plan_request())

    assert setup.plans.added == []
    assert setup.writer.requests == []


def test_trip_days_counts_the_first_and_last_day():
    assert plan_request(days=8).trip_days == 8
    assert plan_request(days=1).trip_days == 1


# Review of #29


async def test_the_read_ends_before_the_model_writes_and_nothing_is_committed():
    setup = Setup(FakeCatalog(ALL), draft(DraftItem(WALK.id, 1, 1, None)))

    await setup.generate(plan_request())

    assert setup.events == ["rollback", "write"]  # the caller commits


class CatalogChangingWriter(FakeWriter):
    """While the model writes, the catalog changes: only `left` still fits."""

    def __init__(self, draft_plan: DraftPlan, catalog: FakeCatalog, left: list[OfferSummary]):
        super().__init__(draft_plan)
        self.catalog = catalog
        self.left = left

    async def write(self, request: PlanRequest) -> DraftPlan | None:
        self.catalog.fitting = self.catalog.ranked = self.left
        return await super().write(request)


def setup_with_changing_catalog(draft_plan: DraftPlan, left: list[OfferSummary]) -> Setup:
    setup = Setup(FakeCatalog(ALL), draft_plan)
    setup.writer = CatalogChangingWriter(draft_plan, setup.catalog, left)
    setup.generate._writer = setup.writer
    return setup


async def test_an_offer_that_stops_fitting_while_the_model_writes_is_dropped():
    setup = setup_with_changing_catalog(
        draft(DraftItem(HOTEL.id, 1, 7, None), DraftItem(WALK.id, 2, 1, None)), left=[WALK]
    )

    view = await setup.generate(plan_request())

    assert [i.offer_id for i in view.items] == [WALK.id]
    assert [i.offer_id for i in setup.plans.added[0].items] == [WALK.id]


async def test_the_fallback_uses_the_catalog_read_after_the_model_writes():
    setup = setup_with_changing_catalog(draft(DraftItem(HOTEL.id, 1, 7, None)), left=[BOAT])

    view = await setup.generate(plan_request())

    assert [i.offer_id for i in view.items] == [BOAT.id]


async def test_when_no_offer_fits_after_the_model_writes_nothing_is_stored():
    setup = setup_with_changing_catalog(draft(DraftItem(HOTEL.id, 1, 7, None)), left=[])

    with pytest.raises(NoOfferFits):
        await setup.generate(plan_request())

    assert setup.plans.added == []


async def test_the_tag_fallback_still_books_a_fitting_hotel():
    setup = Setup(FakeCatalog(ALL, ranked=[BOAT]), None)

    view = await setup.generate(plan_request(days=5))

    assert [(i.offer_id, i.day, i.quantity) for i in view.items] == [
        (HOTEL.id, 1, 4),
        (BOAT.id, 1, 1),
    ]


async def test_hotel_nights_are_cut_to_the_nights_left_and_a_last_day_hotel_is_dropped():
    setup = Setup(
        FakeCatalog(ALL),
        draft(
            DraftItem(HOTEL.id, 3, 30, None),
            DraftItem(HOTEL.id, 8, 1, None),
            DraftItem(WALK.id, 2, 1, None),
        ),
    )

    view = await setup.generate(plan_request(days=8))

    assert [(i.offer_id, i.day, i.quantity) for i in view.items] == [
        (WALK.id, 2, 1),
        (HOTEL.id, 3, 5),
    ]


async def test_duplicate_items_from_the_model_are_kept_once():
    setup = Setup(
        FakeCatalog(ALL),
        draft(
            DraftItem(HOTEL.id, 1, 7, None),
            DraftItem(HOTEL.id, 2, 6, None),
            DraftItem(WALK.id, 2, 1, "Morning"),
            DraftItem(WALK.id, 2, 1, "Again"),
            DraftItem(WALK.id, 3, 1, None),
        ),
    )

    view = await setup.generate(plan_request(days=8))

    assert [(i.offer_id, i.day, i.note) for i in view.items] == [
        (HOTEL.id, 1, None),
        (WALK.id, 2, "Morning"),
        (WALK.id, 3, None),
    ]


async def test_the_model_summary_is_dropped_when_one_of_its_items_was_rejected():
    setup = Setup(
        FakeCatalog(ALL),
        draft(DraftItem(WALK.id, 1, 1, None), DraftItem(UNKNOWN, 2, 1, None), summary="Riad"),
    )

    view = await setup.generate(plan_request())

    assert view.summary != "Riad"
    assert [i.offer_id for i in view.items] == [WALK.id]


async def test_the_model_summary_is_dropped_when_hotel_nights_were_cut():
    setup = Setup(
        FakeCatalog(ALL),
        draft(DraftItem(HOTEL.id, 1, 30, None), DraftItem(WALK.id, 2, 1, None), summary="Long"),
    )

    view = await setup.generate(plan_request(days=5))

    assert view.summary != "Long"
    assert [(i.offer_id, i.quantity) for i in view.items] == [(HOTEL.id, 4), (WALK.id, 1)]


SECOND_HOTEL = OfferSummary(
    UUID("00000000-0000-0000-0000-0000000000b5"),
    "hotel",
    "Old town inn",
    "Rooms",
    (),
    False,
    open_days=EVERY_DAY,
)


async def test_two_hotels_never_book_the_same_night():
    setup = Setup(
        FakeCatalog([*ALL, SECOND_HOTEL]),
        draft(
            DraftItem(HOTEL.id, 3, 2, None),  # nights 3-4
            DraftItem(SECOND_HOTEL.id, 1, 4, None),  # nights 1-4: cut before night 3
        ),
    )

    view = await setup.generate(plan_request(days=5))

    assert [(i.offer_id, i.day, i.quantity) for i in view.items] == [
        (SECOND_HOTEL.id, 1, 2),
        (HOTEL.id, 3, 2),
    ]


async def test_a_hotel_whose_nights_are_all_taken_is_dropped():
    setup = Setup(
        FakeCatalog([*ALL, SECOND_HOTEL]),
        draft(DraftItem(HOTEL.id, 1, 4, None), DraftItem(SECOND_HOTEL.id, 2, 2, None)),
    )

    view = await setup.generate(plan_request(days=5))

    assert [(i.offer_id, i.day, i.quantity) for i in view.items] == [(HOTEL.id, 1, 4)]


# Each item fits its own days (#182)

LATE_BOAT = OfferSummary(
    UUID("00000000-0000-0000-0000-0000000000b6"),
    "activity",
    "Summer boat trip",
    "Open from day 3 of the trip",
    ("style:beach",),
    False,
    open_days=frozenset({3, 4}),
)
GAP_HOTEL = OfferSummary(
    UUID("00000000-0000-0000-0000-0000000000b7"),
    "hotel",
    "Harbour hotel",
    "Full on night 2",
    ("style:beach",),
    False,
    open_days=frozenset({1, 3, 4}),
)


async def test_an_offer_open_on_some_trip_days_is_enough_to_build_a_plan():
    setup = Setup(FakeCatalog([LATE_BOAT]), draft(DraftItem(LATE_BOAT.id, 3, 1, None)))

    view = await setup.generate(plan_request(tags=(), days=4))

    assert [(i.offer_id, i.day) for i in view.items] == [(LATE_BOAT.id, 3)]


async def test_a_model_item_on_a_closed_day_is_dropped_and_one_on_an_open_day_kept():
    setup = Setup(
        FakeCatalog([HOTEL, LATE_BOAT]),
        draft(
            DraftItem(HOTEL.id, 1, 3, None),
            DraftItem(LATE_BOAT.id, 2, 1, None),
            DraftItem(LATE_BOAT.id, 3, 1, None),
        ),
    )

    view = await setup.generate(plan_request(tags=(), days=4))

    assert [(i.offer_id, i.day) for i in view.items] == [(HOTEL.id, 1), (LATE_BOAT.id, 3)]


async def test_a_model_hotel_closed_on_one_of_its_nights_is_dropped():
    setup = Setup(
        FakeCatalog([GAP_HOTEL, WALK]),
        draft(DraftItem(GAP_HOTEL.id, 1, 3, None), DraftItem(WALK.id, 2, 1, None)),
    )

    view = await setup.generate(plan_request(tags=(), days=4))

    assert [(i.offer_id, i.day) for i in view.items] == [(WALK.id, 2)]


async def test_the_fallback_puts_each_offer_only_on_a_day_it_is_open():
    setup = Setup(FakeCatalog([LATE_BOAT, HOTEL, WALK]), None)

    view = await setup.generate(plan_request(tags=(), days=4))

    assert [(i.offer_id, i.day, i.quantity) for i in view.items] == [
        (HOTEL.id, 1, 3),
        (WALK.id, 1, 1),
        (LATE_BOAT.id, 3, 1),
    ]


async def test_the_fallback_skips_a_hotel_not_open_every_night():
    setup = Setup(FakeCatalog([GAP_HOTEL, WALK]), None)

    view = await setup.generate(plan_request(tags=(), days=4))

    assert [(i.offer_id, i.day) for i in view.items] == [(WALK.id, 1)]


async def test_only_hotels_not_open_every_night_raise_no_offer_fits_and_store_nothing():
    # GAP_HOTEL is open on some days, so it fits the trip, but the fallback can't book it
    # every night and there is nothing else: the client gets no_offer_fits, not a broken plan.
    setup = Setup(FakeCatalog([GAP_HOTEL]), None)

    with pytest.raises(NoOfferFits):
        await setup.generate(plan_request(tags=(), days=4))

    assert setup.plans.added == []


async def test_the_fallback_hotel_of_a_one_day_trip_must_be_open_that_day():
    closed_day_one = OfferSummary(
        id=UUID("00000000-0000-0000-0000-00000000c1d1"),
        kind="hotel",
        title="Closed on day one",
        description="",
        tags=(),
        featured=False,
        open_days=frozenset({2}),
    )
    setup = Setup(FakeCatalog([closed_day_one, WALK]), None)

    view = await setup.generate(plan_request(tags=(), days=1))

    assert [(i.offer_id, i.day) for i in view.items] == [(WALK.id, 1)]


# plannable: what the panel asks before sending (#183), the same rule as the fallback


def test_a_trip_with_an_activity_open_on_one_of_its_days_is_plannable():
    from novoya_api.planning.application.use_cases.generate_plan import plannable

    assert plannable([LATE_BOAT], trip_days=4) is True


def test_a_trip_with_only_a_hotel_open_every_night_is_plannable():
    from novoya_api.planning.application.use_cases.generate_plan import plannable

    assert plannable([HOTEL], trip_days=4) is True


def test_a_trip_with_only_hotels_not_open_every_night_is_not_plannable():
    from novoya_api.planning.application.use_cases.generate_plan import plannable

    assert plannable([GAP_HOTEL], trip_days=4) is False
    assert plannable([], trip_days=4) is False
