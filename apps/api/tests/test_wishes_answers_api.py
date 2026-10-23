"""POST /wishes/{id}/answers is tested with the use case built on fakes: no database."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.public import current_user
from novoya_api.main import create_app
from novoya_api.planning.domain.errors import NoOfferFits
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from novoya_api.wishes.application.ports.planner import ProposedItem, ProposedPlan
from novoya_api.wishes.application.use_cases.answer_panel import (
    ANSWER_LIMIT,
    ANSWER_WINDOW,
    AnswerPanel,
)
from novoya_api.wishes.domain.panel import Panel, PanelSection, Tag
from novoya_api.wishes.domain.wish import Destination, Wish, WishStatus
from novoya_api.wishes.infrastructure.answers_in_progress import InMemoryAnswersInProgress
from novoya_api.wishes.presentation.http.dependencies import get_answer_panel, get_current_user_id
from tests.accounts.fakes import FrozenClock
from tests.test_wishes_api import signed_in_as

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("00000000-0000-0000-0000-000000000002")
CREATED = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 19, 9, 5, tzinfo=UTC)
PANEL = Panel(
    sections=(
        PanelSection("style", "Style", True, (Tag("beach", "Beach"), Tag("city", "City"))),
        PanelSection("rhythm", "Rhythm", False, (Tag("slow", "Slow"), Tag("busy", "Busy"))),
    )
)

BODY = {
    "selected_tags": [{"section": "style", "tag": "beach"}, {"section": "rhythm", "tag": "slow"}],
    "budget_max": "1500.50",
    "currency": "EUR",
    "persons": 2,
    "start_date": "2026-11-02",
    "end_date": "2026-11-09",
}


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeWishes:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Wish] = {}
        self.saved: list[Wish] = []

    def put(self, wish: Wish) -> Wish:
        self.by_id[wish.id] = wish
        return wish

    async def get(self, wish_id: UUID) -> Wish | None:
        return self.by_id.get(wish_id)

    async def save(self, wish: Wish) -> None:
        self.saved.append(wish)


PLAN_ID = UUID("00000000-0000-0000-0000-0000000000c1")
ITEM_ID = UUID("00000000-0000-0000-0000-0000000000d1")
OFFER_ID = UUID("00000000-0000-0000-0000-0000000000e1")


class FakePlanner:
    """Proposes a one-item plan for the wish, or raises `error`."""

    def __init__(self) -> None:
        self.error: Exception | None = None

    async def propose(self, wish: Wish) -> ProposedPlan:
        if self.error is not None:
            raise self.error
        item = ProposedItem(
            id=ITEM_ID,
            offer_id=OFFER_ID,
            day=1,
            quantity=7,
            note="Sea view",
            kind="hotel",
            title="Sea view hotel",
            description="Rooms over the bay",
        )
        return ProposedPlan(
            id=PLAN_ID,
            wish_id=wish.id,
            status="proposed",
            based_on_preferences=True,
            summary="A week by the sea",
            items=(item,),
        )


class FakeUnitOfWork:
    async def commit(self) -> None:
        pass


def shown_wish(user_id: UUID = USER_ID) -> Wish:
    wish = Wish.create(user_id, "A week in Lisbon", CREATED)
    wish.show_panel(Destination("Portugal", "Lisbon"), PANEL, CREATED)
    return wish


@pytest.fixture
def wishes() -> FakeWishes:
    return FakeWishes()


@pytest.fixture
def planner() -> FakePlanner:
    return FakePlanner()


@pytest.fixture
def limiter_clock() -> FrozenClock:
    return FrozenClock()


@pytest.fixture
def limiter(limiter_clock) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(limiter_clock)


@pytest.fixture
def app(wishes, planner, limiter):
    app = create_app()
    use_case = AnswerPanel(
        wishes=wishes,
        planner=planner,
        in_progress=InMemoryAnswersInProgress(),
        rate_limiter=limiter,
        uow=FakeUnitOfWork(),
        clock=FixedClock(),
    )
    app.dependency_overrides[get_answer_panel] = lambda: use_case
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    return app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def answer(client: AsyncClient, wish_id: UUID, **changes):
    return await client.post(f"/wishes/{wish_id}/answers", json=BODY | changes)


async def test_answers_are_saved_and_the_proposed_plan_is_returned(wishes, client):
    wish = wishes.put(shown_wish())

    response = await answer(client, wish.id)

    assert response.status_code == 201
    assert response.json() == {
        "id": str(PLAN_ID),
        "wish_id": str(wish.id),
        "status": "proposed",
        "based_on_preferences": True,
        "summary": "A week by the sea",
        "items": [
            {
                "id": str(ITEM_ID),
                "offer_id": str(OFFER_ID),
                "day": 1,
                "quantity": 7,
                "note": "Sea view",
                "kind": "hotel",
                "title": "Sea view hotel",
                "description": "Rooms over the bay",
            }
        ],
    }
    assert wishes.saved == [wish]
    assert wish.status is WishStatus.PLANNED
    assert wish.answers is not None


async def test_the_plan_has_no_price_and_no_partner(wishes, client):
    wish = wishes.put(shown_wish())

    response = await answer(client, wish.id)

    keys = set(response.json()) | {key for item in response.json()["items"] for key in item}
    assert not [key for key in keys if "price" in key or "partner" in key]


async def test_when_no_offer_fits_returns_422_no_offer_fits_and_nothing_is_saved(
    wishes, planner, client
):
    wish = wishes.put(shown_wish())
    planner.error = NoOfferFits("no listed offer fits the travellers and dates")

    response = await answer(client, wish.id)

    assert response.status_code == 422
    assert response.json()["code"] == "no_offer_fits"
    assert wishes.saved == []


async def test_no_tags_is_a_valid_answer(wishes, client):
    wish = wishes.put(shown_wish())

    response = await answer(client, wish.id, selected_tags=[])

    assert response.status_code == 201
    assert wish.answers.selected_tags == ()


async def test_currency_defaults_to_eur(wishes, client):
    wish = wishes.put(shown_wish())
    body = {key: value for key, value in BODY.items() if key != "currency"}

    response = await client.post(f"/wishes/{wish.id}/answers", json=body)

    assert response.status_code == 201
    assert wish.answers.currency == "EUR"


@pytest.mark.parametrize(
    "selected_tags",
    [
        [{"section": "style", "tag": "mountain"}],
        [{"section": "food", "tag": "beach"}],
        [{"section": "rhythm", "tag": "slow"}, {"section": "rhythm", "tag": "busy"}],
    ],
    ids=["unknown tag", "unknown section", "two tags in a single-choice section"],
)
async def test_tags_not_allowed_by_the_panel_return_422_invalid_answers(
    wishes, client, selected_tags
):
    wish = wishes.put(shown_wish())

    response = await answer(client, wish.id, selected_tags=selected_tags)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_answers"
    assert wishes.saved == []
    assert wish.status is WishStatus.PANEL_SHOWN


async def test_end_date_before_start_date_returns_422_invalid_answers(wishes, client):
    wish = wishes.put(shown_wish())

    response = await answer(client, wish.id, end_date="2026-11-01")

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_answers"


@pytest.mark.parametrize(
    "changes",
    [
        {"start_date": "2020-01-01"},
        {"start_date": "2026-10-17"},  # the clock is on 2026-10-19
        {"end_date": "2027-11-03"},  # 367 days, the first and the last included
    ],
    ids=["years ago", "two days ago", "trip too long"],
)
async def test_dates_out_of_range_return_422_invalid_answers(wishes, client, changes):
    wish = wishes.put(shown_wish())

    response = await answer(client, wish.id, **changes)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_answers"
    assert wishes.saved == []
    assert wish.answers is None


@pytest.mark.parametrize(
    "changes",
    [
        {"budget_max": "0"},
        {"budget_max": "-5"},
        {"budget_max": "12.345"},
        {"budget_max": "100000000"},
        {"currency": "USD"},
        {"persons": 0},
        {"persons": 51},
        {"start_date": "next monday"},
        {"selected_tags": [{"section": "", "tag": "beach"}]},
    ],
)
async def test_malformed_answers_return_422(wishes, client, changes):
    wish = wishes.put(shown_wish())

    response = await answer(client, wish.id, **changes)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert wishes.saved == []


async def test_another_users_wish_returns_404(wishes, client):
    wish = wishes.put(shown_wish(user_id=OTHER_ID))

    response = await answer(client, wish.id)

    assert response.status_code == 404
    assert response.json()["code"] == "wish_not_found"
    assert wish.status is WishStatus.PANEL_SHOWN


async def test_an_unknown_wish_returns_404(client):
    response = await answer(client, uuid4())

    assert response.status_code == 404
    assert response.json()["code"] == "wish_not_found"


async def test_answering_twice_returns_409(wishes, client):
    wish = wishes.put(shown_wish())
    await answer(client, wish.id)

    response = await answer(client, wish.id)

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"


async def test_a_wish_without_a_panel_returns_409(wishes, client):
    wish = wishes.put(Wish.create(USER_ID, "Somewhere warm", CREATED))

    response = await answer(client, wish.id)

    assert response.status_code == 409


async def test_without_a_signed_in_user_returns_401(app, wishes, client):
    del app.dependency_overrides[get_current_user_id]
    wish = wishes.put(shown_wish())

    response = await answer(client, wish.id)

    assert response.status_code == 401
    assert wishes.saved == []


@pytest.mark.parametrize(
    ("role", "status"), [(Role.CLIENT, 201), (Role.ADMIN, 201), (Role.AGENT, 403)]
)
async def test_only_clients_and_admins_answer(app, wishes, client, role, status):
    del app.dependency_overrides[get_current_user_id]
    app.dependency_overrides[current_user] = lambda: signed_in_as(role)
    wish = wishes.put(shown_wish())

    response = await answer(client, wish.id)

    assert response.status_code == status


def test_answer_panel_route_is_documented_with_the_shared_error_responses(app):
    operation = app.openapi()["paths"]["/wishes/{wish_id}/answers"]["post"]

    assert operation["operationId"] == "answerPanel"
    assert operation["tags"] == ["wishes"]
    created = operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    assert created == "#/components/schemas/PlanResponse"
    for status in ("401", "403", "404", "409", "422"):
        ref = operation["responses"][status]["content"]["application/json"]["schema"]["$ref"]
        assert ref == "#/components/schemas/ErrorResponse", status


# Rate limit


async def test_past_the_limit_returns_429_with_retry_after(wishes, planner, client):
    for _ in range(ANSWER_LIMIT):
        assert (await answer(client, uuid4())).status_code == 404  # rejected answers count
    wish = wishes.put(shown_wish())

    response = await answer(client, wish.id)

    assert response.status_code == 429
    assert response.json()["code"] == "too_many_requests"
    assert response.headers["Retry-After"] == str(int(ANSWER_WINDOW.total_seconds()))
    assert wish.status is WishStatus.PANEL_SHOWN


async def test_another_client_still_answers_when_one_is_limited(app, wishes, client):
    for _ in range(ANSWER_LIMIT + 1):
        await answer(client, uuid4())
    app.dependency_overrides[get_current_user_id] = lambda: OTHER_ID
    wish = wishes.put(shown_wish(user_id=OTHER_ID))

    response = await answer(client, wish.id)

    assert response.status_code == 201


def test_answer_panel_documents_429(app):
    operation = app.openapi()["paths"]["/wishes/{wish_id}/answers"]["post"]

    ref = operation["responses"]["429"]["content"]["application/json"]["schema"]["$ref"]
    assert ref == "#/components/schemas/ErrorResponse"
