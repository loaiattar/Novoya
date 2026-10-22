"""The admin overview use cases (#130) on fakes: how the search and the filters combine."""

from datetime import UTC, datetime
from uuid import uuid4

from novoya_api.planning.application.use_cases.list_admin_plans import ListAdminPlans
from novoya_api.quoting.application.use_cases.list_admin_quotes import ListAdminQuotes
from novoya_api.quoting.domain.quote import QuoteStatus

NOW = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)


class FakePlans:
    def __init__(self) -> None:
        self.searches: list[tuple] = []

    async def search(self, statuses, wish_ids, *, limit, offset):
        self.searches.append((list(statuses), wish_ids))
        return []


class EmptyTrips:
    async def for_wish_ids(self, wish_ids):
        return {}


class FakeWishSearch:
    def __init__(self, found) -> None:
        self.found = found
        self.calls: list[tuple] = []

    async def matching(self, query, user_ids):
        self.calls.append((query, list(user_ids)))
        return self.found


class FakePeople:
    def __init__(self, user_ids=()) -> None:
        self.user_ids = list(user_ids)

    async def search_ids(self, query):
        return self.user_ids

    async def get_many(self, user_ids):
        return {}


def plans_use_case(found_wishes=()):
    plans, search = FakePlans(), FakeWishSearch(list(found_wishes))
    alice = uuid4()
    return ListAdminPlans(plans, EmptyTrips(), search, FakePeople([alice])), plans, search, alice


async def test_a_plan_search_passes_the_matching_clients_to_the_wish_search():
    use_case, plans, search, alice = plans_use_case([uuid4()])

    await use_case(query="  alice  ")

    assert search.calls == [("alice", [alice])]
    assert plans.searches[0][1] == search.found


async def test_a_plan_search_without_a_matching_wish_reads_no_plan():
    use_case, plans, _, _ = plans_use_case([])

    assert await use_case(query="nowhere") == []
    assert plans.searches == []


async def test_without_a_search_every_wish_is_read():
    use_case, plans, search, _ = plans_use_case()

    await use_case()

    assert search.calls == []
    assert plans.searches == [([], None)]


async def test_one_wish_outside_the_search_gives_nothing():
    use_case, plans, _, _ = plans_use_case([uuid4()])

    assert await use_case(query="alice", wish_id=uuid4()) == []
    assert plans.searches == []


class FakeQuotes:
    def __init__(self) -> None:
        self.searches: list[tuple] = []

    async def search(self, plan_ids, status, now, *, limit, offset):
        self.searches.append((plan_ids, status, now))
        return []


class FakePlanQuoting:
    def __init__(self, found) -> None:
        self.found = found
        self.calls: list[tuple] = []

    async def find_ids(self, query, user_ids):
        self.calls.append((query, list(user_ids)))
        return self.found

    async def trips(self, plan_ids):
        return {}


class FixedClock:
    def now(self):
        return NOW


def quotes_use_case(found=()):
    quotes, plans = FakeQuotes(), FakePlanQuoting(list(found))
    return ListAdminQuotes(quotes, plans, FakePeople(), FixedClock()), quotes, plans


async def test_the_status_filter_reads_the_quotes_without_searching_the_plans():
    use_case, quotes, plans = quotes_use_case()

    for status in QuoteStatus:
        await use_case(status)

    assert plans.calls == []
    assert quotes.searches == [(None, status, NOW) for status in QuoteStatus]


async def test_the_search_goes_through_the_plans():
    plan_id = uuid4()
    use_case, quotes, plans = quotes_use_case([plan_id])

    await use_case(QuoteStatus.OPEN, query=" crete ")

    assert plans.calls[0][0] == "crete"
    assert quotes.searches == [([plan_id], QuoteStatus.OPEN, NOW)]


async def test_without_a_filter_every_quote_is_read():
    use_case, quotes, plans = quotes_use_case()

    await use_case()

    assert plans.calls == []
    assert quotes.searches == [(None, None, NOW)]


async def test_no_matching_plan_reads_no_quote():
    use_case, quotes, _ = quotes_use_case([])

    assert await use_case(query="nowhere") == []
    assert quotes.searches == []
