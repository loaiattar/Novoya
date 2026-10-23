from datetime import UTC, datetime
from uuid import UUID, uuid4

from novoya_api.trips.application.dto import PlanSummary, WishSummary
from novoya_api.trips.application.use_cases.list_my_trips import ListMyTrips

USER = uuid4()


def a_wish(text: str = "Une semaine en Crete") -> WishSummary:
    return WishSummary(
        wish_id=uuid4(),
        text=text,
        status="answered",
        country="Grece",
        city="Chania",
        persons=2,
        start_date=None,
        end_date=None,
        created_at=datetime(2026, 10, 1, tzinfo=UTC),
    )


class FakeWishes:
    def __init__(self, wishes: list[WishSummary]) -> None:
        self.wishes = wishes
        self.asked_for: list[UUID] = []

    async def of_user(self, user_id: UUID) -> list[WishSummary]:
        self.asked_for.append(user_id)
        return self.wishes


class FakePlans:
    def __init__(self, plans: dict[UUID, PlanSummary]) -> None:
        self.plans = plans

    async def for_wishes(self, wish_ids):
        return {wish_id: self.plans[wish_id] for wish_id in wish_ids if wish_id in self.plans}


class FakeQuotes:
    def __init__(self, quotes: dict[UUID, UUID]) -> None:
        self.quotes = quotes

    async def for_plans(self, plan_ids):
        return {plan_id: self.quotes[plan_id] for plan_id in plan_ids if plan_id in self.quotes}


async def test_a_client_without_wishes_has_no_trips():
    use_case = ListMyTrips(FakeWishes([]), FakePlans({}), FakeQuotes({}))

    assert await use_case(USER) == []


async def test_the_wishes_of_the_signed_in_client_are_read():
    wishes = FakeWishes([])

    await ListMyTrips(wishes, FakePlans({}), FakeQuotes({}))(USER)

    assert wishes.asked_for == [USER]


async def test_a_wish_without_plan_has_no_plan_and_no_quote():
    wish = a_wish()
    use_case = ListMyTrips(FakeWishes([wish]), FakePlans({}), FakeQuotes({}))

    [trip] = await use_case(USER)

    assert (trip.wish_id, trip.text, trip.status) == (wish.wish_id, wish.text, "answered")
    assert (trip.plan_id, trip.plan_status, trip.quote_id) == (None, None, None)


async def test_a_wish_with_a_plan_but_no_quote_gives_the_plan():
    wish = a_wish()
    plan = PlanSummary(uuid4(), "proposed")
    use_case = ListMyTrips(FakeWishes([wish]), FakePlans({wish.wish_id: plan}), FakeQuotes({}))

    [trip] = await use_case(USER)

    assert (trip.plan_id, trip.plan_status, trip.quote_id) == (plan.plan_id, "proposed", None)


async def test_a_quoted_wish_gives_its_plan_and_its_quote():
    wish = a_wish()
    plan = PlanSummary(uuid4(), "quoted")
    quote_id = uuid4()
    use_case = ListMyTrips(
        FakeWishes([wish]), FakePlans({wish.wish_id: plan}), FakeQuotes({plan.plan_id: quote_id})
    )

    [trip] = await use_case(USER)

    assert (trip.plan_id, trip.plan_status, trip.quote_id) == (plan.plan_id, "quoted", quote_id)


async def test_the_order_of_the_wishes_is_kept():
    newest, oldest = a_wish("newest"), a_wish("oldest")
    use_case = ListMyTrips(FakeWishes([newest, oldest]), FakePlans({}), FakeQuotes({}))

    trips = await use_case(USER)

    assert [trip.text for trip in trips] == ["newest", "oldest"]
