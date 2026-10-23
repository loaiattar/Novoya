"""When no offer fits (#184): SendCustomRequest and GetClosestDates on fakes, and their routes
POST /wishes/{id}/custom-request and GET /wishes/{id}/closest-dates. No database."""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.main import create_app
from novoya_api.shared.domain.errors import InvalidTransition
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from novoya_api.wishes.application.dto import DateOption
from novoya_api.wishes.application.ports.planner import CustomRequest
from novoya_api.wishes.application.use_cases.answer_panel import ANSWER_LIMIT, AnswerPanelCommand
from novoya_api.wishes.application.use_cases.closest_dates import GetClosestDates
from novoya_api.wishes.application.use_cases.send_custom_request import SendCustomRequest
from novoya_api.wishes.domain.answers import Answers, SelectedTag
from novoya_api.wishes.domain.errors import InvalidAnswers, WishNotFound
from novoya_api.wishes.domain.panel import Panel
from novoya_api.wishes.domain.wish import Destination, Wish, WishStatus
from novoya_api.wishes.infrastructure.answers_in_progress import InMemoryAnswersInProgress
from novoya_api.wishes.presentation.http.dependencies import (
    get_closest_dates,
    get_current_user_id,
    get_send_custom_request,
)
from tests.accounts.fakes import FrozenClock

OWNER = UUID("00000000-0000-0000-0000-000000000001")
OTHER = UUID("00000000-0000-0000-0000-000000000002")
CREATED = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 19, 9, 5, tzinfo=UTC)
TODAY = date(2026, 10, 19)
CHANIA = Destination("Greece", "Chania")
PANEL = Panel.from_tags(["style:hiking", "style:beach"])
ANSWERS = Answers(
    selected_tags=(SelectedTag("style", "hiking"),),
    budget_max=Decimal("9000"),
    currency="EUR",
    persons=10,
    start_date=date(2026, 11, 2),
    end_date=date(2026, 11, 8),
)
BODY = {
    "selected_tags": [{"section": "style", "tag": "hiking"}],
    "budget_max": "9000",
    "currency": "EUR",
    "persons": 10,
    "start_date": "2026-11-02",
    "end_date": "2026-11-08",
}


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeWishes:
    def __init__(self, events: list[str], *wishes: Wish) -> None:
        self.events = events
        self.by_id = {wish.id: wish for wish in wishes}
        self.saved: list[Wish] = []

    async def get(self, wish_id: UUID) -> Wish | None:
        return self.by_id.get(wish_id)

    async def save(self, wish: Wish) -> None:
        self.events.append("save")
        self.saved.append(wish)


class FakePlanner:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.requested: list[CustomRequest] = []
        self.confirmed: list[tuple[UUID, UUID]] = []
        self.statuses: list[WishStatus] = []

    async def request_custom(self, wish: Wish) -> CustomRequest:
        self.events.append("request_custom")
        self.statuses.append(wish.status)
        plan = CustomRequest(id=uuid4(), wish_id=wish.id, status="requested")
        self.requested.append(plan)
        return plan

    async def confirm(self, plan_id: UUID, user_id: UUID) -> None:
        self.events.append("confirm")
        self.confirmed.append((plan_id, user_id))


class FakeUnitOfWork:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def commit(self) -> None:
        self.events.append("commit")


def shown_wish(user_id: UUID = OWNER) -> Wish:
    wish = Wish.create(user_id, "Ten of us, a week of hiking in Crete", CREATED)
    wish.show_panel(CHANIA, PANEL, CREATED)
    return wish


class Limiter:
    """Records each hit and never refuses."""

    def __init__(self) -> None:
        self.hits: list[tuple[str, int]] = []

    @property
    def keys(self) -> list[str]:
        return [key for key, _limit in self.hits]

    async def hit(self, key: str, limit: int, window) -> None:
        self.hits.append((key, limit))


class Setup:
    def __init__(self, *wishes: Wish, limiter=None) -> None:
        self.events: list[str] = []
        self.wishes = FakeWishes(self.events, *wishes)
        self.planner = FakePlanner(self.events)
        self.use_case = SendCustomRequest(
            wishes=self.wishes,
            planner=self.planner,
            in_progress=InMemoryAnswersInProgress(),
            rate_limiter=limiter or InMemoryRateLimiter(FrozenClock()),
            uow=FakeUnitOfWork(self.events),
            clock=FixedClock(),
        )

    async def send(self, wish_id: UUID, user_id: UUID = OWNER, answers: Answers = ANSWERS):
        return await self.use_case(
            AnswerPanelCommand(user_id=user_id, wish_id=wish_id, answers=answers)
        )


async def test_the_answers_and_the_custom_plan_are_committed_then_the_client_is_emailed():
    wish = shown_wish()
    setup = Setup(wish)

    result = await setup.send(wish.id)

    assert setup.events == ["request_custom", "save", "commit", "confirm"]
    assert setup.planner.statuses == [WishStatus.ANSWERED]
    assert result.wish.status is WishStatus.PLANNED
    assert result.wish.answers == ANSWERS
    assert result.plan.status == "requested"
    assert setup.planner.confirmed == [(result.plan.id, OWNER)]


async def test_a_second_send_is_refused_and_creates_no_second_request():
    wish = shown_wish()
    setup = Setup(wish)
    await setup.send(wish.id)

    with pytest.raises(InvalidTransition):
        await setup.send(wish.id)
    assert len(setup.planner.requested) == 1
    assert len(setup.planner.confirmed) == 1


async def test_another_clients_wish_is_not_found_and_left_untouched():
    wish = shown_wish(OTHER)
    setup = Setup(wish)

    with pytest.raises(WishNotFound):
        await setup.send(wish.id)
    assert setup.events == []
    assert wish.status is WishStatus.PANEL_SHOWN


async def test_dates_in_the_past_are_refused_before_anything_runs():
    wish = shown_wish()
    setup = Setup(wish)
    past = replace(ANSWERS, start_date=date(2026, 1, 2))

    with pytest.raises(InvalidAnswers):
        await setup.send(wish.id, answers=past)
    assert setup.events == []


async def test_it_counts_against_the_same_limit_as_the_answers():
    wish = shown_wish()
    limiter = Limiter()
    setup = Setup(wish, limiter=limiter)

    await setup.send(wish.id)

    assert limiter.hits == [(f"wishes:answer:{OWNER}", ANSWER_LIMIT)]


class FakeCatalog:
    def __init__(self, options: list[DateOption]) -> None:
        self.options = options
        self.calls: list[tuple] = []

    async def closest_dates(self, destination, persons, start, end, earliest):
        self.calls.append((destination, persons, start, end, earliest))
        return self.options


OPTIONS = [
    DateOption(date(2026, 10, 26), date(2026, 11, 1), 3),
    DateOption(date(2026, 11, 16), date(2026, 11, 22), 5),
]


async def test_the_closest_dates_come_from_the_catalog_from_today_on():
    wish = shown_wish()
    catalog, limiter = FakeCatalog(OPTIONS), Limiter()
    use_case = GetClosestDates(FakeWishes([], wish), catalog, FixedClock(), limiter)

    found = await use_case(wish.id, OWNER, 10, date(2026, 11, 2), date(2026, 11, 8))

    assert found == OPTIONS
    assert catalog.calls == [(CHANIA, 10, date(2026, 11, 2), date(2026, 11, 8), TODAY)]
    assert limiter.keys == [f"wishes:dates:{OWNER}"]


async def test_the_closest_dates_of_another_clients_wish_are_not_found():
    wish = shown_wish(OTHER)
    catalog = FakeCatalog(OPTIONS)
    use_case = GetClosestDates(FakeWishes([], wish), catalog, FixedClock(), Limiter())

    with pytest.raises(WishNotFound):
        await use_case(wish.id, OWNER, 10, date(2026, 11, 2), date(2026, 11, 8))
    assert catalog.calls == []


async def test_the_closest_dates_refuse_dates_the_answer_would_refuse():
    wish = shown_wish()
    catalog = FakeCatalog(OPTIONS)
    use_case = GetClosestDates(FakeWishes([], wish), catalog, FixedClock(), Limiter())

    with pytest.raises(InvalidAnswers):
        await use_case(wish.id, OWNER, 10, date(2026, 11, 8), date(2026, 11, 2))
    assert catalog.calls == []


# The routes


@pytest.fixture
def setup() -> Setup:
    return Setup(shown_wish())


@pytest.fixture
def app(setup):
    app = create_app()
    [wish] = setup.wishes.by_id.values()
    dates = GetClosestDates(FakeWishes([], wish), FakeCatalog(OPTIONS), FixedClock(), Limiter())
    app.dependency_overrides[get_current_user_id] = lambda: OWNER
    app.dependency_overrides[get_send_custom_request] = lambda: setup.use_case
    app.dependency_overrides[get_closest_dates] = lambda: dates
    return app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_post_custom_request_answers_201_with_the_requested_plan(client, setup):
    [wish] = setup.wishes.by_id.values()

    response = await client.post(f"/wishes/{wish.id}/custom-request", json=BODY)

    assert response.status_code == 201
    [plan] = setup.planner.requested
    assert response.json() == {"id": str(plan.id), "wish_id": str(wish.id), "status": "requested"}


async def test_a_second_post_is_409_and_sends_nothing_more(client, setup):
    [wish] = setup.wishes.by_id.values()
    await client.post(f"/wishes/{wish.id}/custom-request", json=BODY)

    response = await client.post(f"/wishes/{wish.id}/custom-request", json=BODY)

    assert response.status_code == 409
    assert len(setup.planner.requested) == 1


async def test_get_closest_dates_lists_them_and_is_not_cached(client, setup):
    [wish] = setup.wishes.by_id.values()

    response = await client.get(
        f"/wishes/{wish.id}/closest-dates",
        params={"persons": 10, "start_date": "2026-11-02", "end_date": "2026-11-08"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json() == [
        {"start_date": "2026-10-26", "end_date": "2026-11-01", "offers": 3},
        {"start_date": "2026-11-16", "end_date": "2026-11-22", "offers": 5},
    ]


async def test_get_closest_dates_needs_the_travellers_and_both_dates(client, setup):
    [wish] = setup.wishes.by_id.values()

    response = await client.get(
        f"/wishes/{wish.id}/closest-dates", params={"start_date": "2026-11-02"}
    )

    assert response.status_code == 422
