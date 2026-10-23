"""The preference panel's limits from the catalog (#183): GetPanelLimits on fakes and the
GET /wishes/{wish_id}/limits route. No database: see test_wishes_catalog_sql.py."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.public import current_user
from novoya_api.main import create_app
from novoya_api.shared.domain.errors import TooManyRequests
from novoya_api.wishes.application.dto import PanelLimits, PanelLimitsView
from novoya_api.wishes.application.use_cases.get_panel_limits import GetPanelLimits
from novoya_api.wishes.domain.errors import InvalidAnswers, WishNotFound
from novoya_api.wishes.domain.panel import Panel
from novoya_api.wishes.domain.wish import Destination, Wish
from novoya_api.wishes.presentation.http.dependencies import (
    get_current_user_id,
    get_panel_limits,
)
from tests.test_wishes_api import signed_in_as

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("00000000-0000-0000-0000-000000000002")
CREATED = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)
TODAY = date(2026, 10, 23)
LISBON = Destination("Portugal", "Lisbon")
PANEL = Panel.from_tags(["style:beach", "style:city"])
LIMITS = PanelLimits(
    persons_min=1,
    persons_max=8,
    first_date=TODAY,
    last_date=date(2027, 3, 31),
    open_months=(1, 2, 3, 10, 11, 12),
)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeWishes:
    def __init__(self, *wishes: Wish) -> None:
        self.by_id = {wish.id: wish for wish in wishes}

    async def get(self, wish_id: UUID) -> Wish | None:
        return self.by_id.get(wish_id)


class FakeCatalog:
    """Returns `limits` and `fitting`, and records what it was asked."""

    def __init__(self, limits: PanelLimits | None = LIMITS, fitting: bool = True) -> None:
        self.limits_returned = limits
        self.fitting = fitting
        self.limits_calls: list[tuple[Destination, date, int | None]] = []
        self.fits_calls: list[tuple[Destination, int, date, date]] = []

    async def limits(
        self, destination: Destination, today: date, persons: int | None = None
    ) -> PanelLimits | None:
        self.limits_calls.append((destination, today, persons))
        return self.limits_returned

    async def fits(self, destination: Destination, persons: int, start: date, end: date) -> bool:
        self.fits_calls.append((destination, persons, start, end))
        return self.fitting


def shown_wish(user_id: UUID = USER_ID) -> Wish:
    wish = Wish.create(user_id, "A week in Lisbon", CREATED)
    wish.show_panel(LISBON, PANEL, CREATED)
    return wish


def draft_wish(user_id: UUID = USER_ID) -> Wish:
    return Wish.create(user_id, "Somewhere warm", CREATED)


class FakeLimiter:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.keys: list[str] = []

    async def hit(self, key: str, limit: int, window: timedelta) -> None:
        self.keys.append(key)
        if self.error:
            raise self.error


def get_limits(
    wishes: FakeWishes, catalog: FakeCatalog, limiter: FakeLimiter | None = None
) -> GetPanelLimits:
    return GetPanelLimits(
        wishes=wishes, catalog=catalog, clock=FixedClock(), rate_limiter=limiter or FakeLimiter()
    )


# The server's day is UTC: one day earlier can still be today for the client (START_TOLERANCE).
FROM_DAY = TODAY - timedelta(days=1)


# The use case


async def test_the_owner_gets_the_limits_of_the_wish_destination_from_today():
    wish = shown_wish()
    catalog = FakeCatalog()

    view = await get_limits(FakeWishes(wish), catalog)(wish.id, USER_ID)

    assert view == PanelLimitsView(limits=LIMITS, fits=None)
    assert catalog.limits_calls == [(LISBON, FROM_DAY, None)]
    assert catalog.fits_calls == []


@pytest.mark.parametrize("fitting", [True, False])
async def test_with_travellers_and_dates_fits_is_the_catalog_answer(fitting):
    wish = shown_wish()
    catalog = FakeCatalog(fitting=fitting)

    view = await get_limits(FakeWishes(wish), catalog)(
        wish.id, USER_ID, persons=3, start=date(2027, 1, 10), end=date(2027, 1, 17)
    )

    assert view.fits is fitting
    assert view.limits == LIMITS
    assert catalog.fits_calls == [(LISBON, 3, date(2027, 1, 10), date(2027, 1, 17))]


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2027, 1, 17), date(2027, 1, 10)),  # the end before the start
        (date(2027, 1, 10), date(2027, 1, 10)),  # a trip needs a night
        (TODAY - timedelta(days=2), TODAY + timedelta(days=5)),  # in the past for everyone
        (date(2027, 1, 1), date(2028, 1, 2)),  # 367 days
    ],
)
async def test_dates_the_answer_would_refuse_are_refused_without_asking_the_catalog(start, end):
    # The same rules as the answer, so the check never says yes to dates it would refuse,
    # and a request can't make the catalog walk centuries.
    wish = shown_wish()
    catalog = FakeCatalog(fitting=True)

    with pytest.raises(InvalidAnswers):
        await get_limits(FakeWishes(wish), catalog)(wish.id, USER_ID, 2, start, end)
    assert catalog.fits_calls == []


async def test_a_departure_yesterday_is_still_checked_it_can_be_today_for_the_client():
    wish = shown_wish()
    catalog = FakeCatalog(fitting=True)

    view = await get_limits(FakeWishes(wish), catalog)(
        wish.id, USER_ID, 2, FROM_DAY, FROM_DAY + timedelta(days=3)
    )

    assert view.fits is True


async def test_with_travellers_the_limits_are_those_of_the_offers_taking_them():
    wish = shown_wish()
    catalog = FakeCatalog()

    await get_limits(FakeWishes(wish), catalog)(
        wish.id, USER_ID, 3, date(2027, 1, 10), date(2027, 1, 17)
    )

    assert catalog.limits_calls == [(LISBON, FROM_DAY, 3)]


async def test_group_limits_stop_at_the_panels_fifty_travellers():
    wish = shown_wish()
    big = PanelLimits(1, 200, TODAY, date(2027, 3, 31), (1, 2, 3))

    view = await get_limits(FakeWishes(wish), FakeCatalog(limits=big))(wish.id, USER_ID)

    assert view.limits == PanelLimits(1, 50, TODAY, date(2027, 3, 31), (1, 2, 3))


async def test_offers_all_for_more_than_fifty_travellers_leave_no_limits():
    wish = shown_wish()
    venues = PanelLimits(60, 200, TODAY, date(2027, 3, 31), (1, 2, 3))

    view = await get_limits(FakeWishes(wish), FakeCatalog(limits=venues))(wish.id, USER_ID)

    assert view.limits is None


async def test_each_read_counts_against_the_clients_own_limit():
    wish = shown_wish()
    limiter = FakeLimiter()

    await get_limits(FakeWishes(wish), FakeCatalog(), limiter)(wish.id, USER_ID)

    assert limiter.keys == [f"wishes:limits:{USER_ID}"]


async def test_past_the_limit_the_catalog_is_not_read():
    wish = shown_wish()
    catalog = FakeCatalog()

    with pytest.raises(TooManyRequests):
        await get_limits(FakeWishes(wish), catalog, FakeLimiter(TooManyRequests(30)))(
            wish.id, USER_ID
        )
    assert catalog.limits_calls == []


@pytest.mark.parametrize(
    ("persons", "start", "end"),
    [
        (2, None, None),
        (None, date(2027, 1, 10), date(2027, 1, 17)),
        (2, date(2027, 1, 10), None),
    ],
)
async def test_fits_is_none_unless_travellers_and_both_dates_are_given(persons, start, end):
    wish = shown_wish()
    catalog = FakeCatalog()

    view = await get_limits(FakeWishes(wish), catalog)(
        wish.id, USER_ID, persons=persons, start=start, end=end
    )

    assert view.fits is None
    assert catalog.fits_calls == []


async def test_another_clients_wish_is_not_found():
    wish = shown_wish(OTHER_ID)
    catalog = FakeCatalog()

    with pytest.raises(WishNotFound):
        await get_limits(FakeWishes(wish), catalog)(wish.id, USER_ID)
    assert catalog.limits_calls == []


async def test_a_missing_wish_is_not_found():
    with pytest.raises(WishNotFound):
        await get_limits(FakeWishes(), FakeCatalog())(uuid4(), USER_ID)


async def test_a_wish_without_a_destination_is_not_found():
    wish = draft_wish()
    catalog = FakeCatalog()

    with pytest.raises(WishNotFound):
        await get_limits(FakeWishes(wish), catalog)(wish.id, USER_ID)
    assert catalog.limits_calls == []


async def test_no_listed_offer_left_means_no_limits():
    wish = shown_wish()

    view = await get_limits(FakeWishes(wish), FakeCatalog(limits=None))(wish.id, USER_ID)

    assert view == PanelLimitsView(limits=None, fits=None)


# The route


@pytest.fixture
def mine() -> Wish:
    return shown_wish(USER_ID)


@pytest.fixture
def theirs() -> Wish:
    return shown_wish(OTHER_ID)


@pytest.fixture
def catalog() -> FakeCatalog:
    return FakeCatalog(fitting=True)


@pytest.fixture
def app(mine, theirs, catalog):
    app = create_app()
    use_case = get_limits(FakeWishes(mine, theirs), catalog)
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_panel_limits] = lambda: use_case
    return app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_get_limits_returns_the_limits_and_is_not_cached(client, mine):
    response = await client.get(f"/wishes/{mine.id}/limits")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json() == {
        "persons_min": 1,
        "persons_max": 8,
        "first_date": "2026-10-23",
        "last_date": "2027-03-31",
        "open_months": [1, 2, 3, 10, 11, 12],
        "fits": None,
    }


async def test_get_limits_with_travellers_and_dates_says_whether_they_fit(client, mine, catalog):
    response = await client.get(
        f"/wishes/{mine.id}/limits",
        params={"persons": 3, "start_date": "2027-01-10", "end_date": "2027-01-17"},
    )

    assert response.status_code == 200
    assert response.json()["fits"] is True
    assert catalog.fits_calls == [(LISBON, 3, date(2027, 1, 10), date(2027, 1, 17))]


async def test_get_limits_without_listed_offers_has_empty_limits(app, client, mine):
    app.dependency_overrides[get_panel_limits] = lambda: get_limits(
        FakeWishes(mine), FakeCatalog(limits=None)
    )

    response = await client.get(f"/wishes/{mine.id}/limits")

    assert response.status_code == 200
    assert response.json() == {
        "persons_min": None,
        "persons_max": None,
        "first_date": None,
        "last_date": None,
        "open_months": [],
        "fits": None,
    }


@pytest.mark.parametrize(
    "params",
    [
        {"persons": 2},
        {"start_date": "2027-01-10", "end_date": "2027-01-17"},
        {"persons": 2, "start_date": "2027-01-10"},
        {"end_date": "2027-01-17"},
    ],
)
async def test_get_limits_with_only_some_of_travellers_and_dates_is_422(client, mine, params):
    response = await client.get(f"/wishes/{mine.id}/limits", params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


@pytest.mark.parametrize("persons", [0, 51])
async def test_get_limits_with_travellers_out_of_range_is_422(client, mine, persons):
    response = await client.get(
        f"/wishes/{mine.id}/limits",
        params={"persons": persons, "start_date": "2027-01-10", "end_date": "2027-01-17"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


async def test_get_limits_of_another_clients_wish_is_404(client, theirs, catalog):
    response = await client.get(f"/wishes/{theirs.id}/limits")

    assert response.status_code == 404
    assert response.json()["code"] == "wish_not_found"
    assert catalog.limits_calls == []


async def test_get_limits_of_an_unknown_wish_is_404(client):
    response = await client.get(f"/wishes/{uuid4()}/limits")

    assert response.status_code == 404
    assert response.json()["code"] == "wish_not_found"


async def test_get_limits_needs_a_session(app, client, mine):
    del app.dependency_overrides[get_current_user_id]

    assert (await client.get(f"/wishes/{mine.id}/limits")).status_code == 401


async def test_an_agent_cannot_read_panel_limits(app, client, mine):
    del app.dependency_overrides[get_current_user_id]
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.AGENT)

    assert (await client.get(f"/wishes/{mine.id}/limits")).status_code == 403


def test_get_limits_is_in_the_openapi_schema_as_get_panel_limits():
    schema = create_app().openapi()

    operation = schema["paths"]["/wishes/{wish_id}/limits"]["get"]
    assert operation["operationId"] == "getPanelLimits"


@pytest.mark.parametrize(
    "params",
    [
        {"persons": 2, "start_date": "2027-01-17", "end_date": "2027-01-10"},
        {"persons": 2, "start_date": "2027-01-01", "end_date": "2028-01-02"},
    ],
)
async def test_get_limits_with_dates_the_answer_would_refuse_is_422(client, mine, params):
    response = await client.get(f"/wishes/{mine.id}/limits", params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_answers"
