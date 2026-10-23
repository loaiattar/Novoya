"""AnswerPanel is tested with fake ports: an in-memory repository, planner and unit of work."""

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from novoya_api.planning.domain.errors import NoOfferFits
from novoya_api.shared.domain.errors import (
    Conflict,
    InvalidTransition,
    NotFound,
    TooManyRequests,
)
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from novoya_api.wishes.application.ports.planner import ProposedItem, ProposedPlan
from novoya_api.wishes.application.use_cases.answer_panel import (
    ANSWER_LIMIT,
    ANSWER_WINDOW,
    AnswerPanel,
    AnswerPanelCommand,
    AnswerPanelResult,
)
from novoya_api.wishes.domain.answers import Answers, SelectedTag
from novoya_api.wishes.domain.errors import AnswerInProgress, InvalidAnswers, WishNotFound
from novoya_api.wishes.domain.panel import Panel
from novoya_api.wishes.domain.wish import Destination, Wish, WishStatus
from novoya_api.wishes.infrastructure.answers_in_progress import InMemoryAnswersInProgress
from tests.accounts.fakes import FrozenClock

OWNER = UUID("00000000-0000-0000-0000-000000000001")
OTHER = UUID("00000000-0000-0000-0000-000000000002")
CREATED = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 19, 9, 5, tzinfo=UTC)
PANEL = Panel.from_tags(["style:beach", "style:city"])
ANSWERS = Answers(
    selected_tags=(SelectedTag("style", "beach"),),
    budget_max=Decimal("1500"),
    currency="EUR",
    persons=2,
    start_date=date(2026, 11, 2),
    end_date=date(2026, 11, 9),
)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeWishes:
    def __init__(self, events: list[str], wishes: list[Wish]) -> None:
        self.events = events
        self.by_id = {wish.id: wish for wish in wishes}
        self.saved: list[Wish] = []

    async def get(self, wish_id: UUID) -> Wish | None:
        return self.by_id.get(wish_id)

    async def save(self, wish: Wish) -> None:
        self.events.append("save")
        self.saved.append(wish)


def proposed_plan(wish_id: UUID) -> ProposedPlan:
    item = ProposedItem(
        id=uuid4(),
        offer_id=uuid4(),
        day=1,
        quantity=7,
        note=None,
        kind="hotel",
        title="Sea view hotel",
        description="Rooms over the bay",
    )
    return ProposedPlan(
        id=uuid4(),
        wish_id=wish_id,
        status="proposed",
        based_on_preferences=True,
        summary="A week by the sea",
        items=(item,),
    )


class FakePlanner:
    """Proposes a plan, or raises `error`. Records the wish's status when it is called."""

    def __init__(self, events: list[str], error: Exception | None = None) -> None:
        self.events = events
        self.error = error
        self.proposed: list[ProposedPlan] = []
        self.statuses: list[WishStatus] = []

    async def propose(self, wish: Wish) -> ProposedPlan:
        self.events.append("propose")
        self.statuses.append(wish.status)
        if self.error is not None:
            raise self.error
        plan = proposed_plan(wish.id)
        self.proposed.append(plan)
        return plan


class FakeUnitOfWork:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def commit(self) -> None:
        self.events.append("commit")


class Setup:
    def __init__(self, *wishes: Wish, planner_error: Exception | None = None) -> None:
        self.events: list[str] = []
        self.wishes = FakeWishes(self.events, list(wishes))
        self.planner = FakePlanner(self.events, planner_error)
        self.limiter_clock = FrozenClock()
        self.limiter = InMemoryRateLimiter(self.limiter_clock)
        self.answer_panel = AnswerPanel(
            wishes=self.wishes,
            planner=self.planner,
            in_progress=InMemoryAnswersInProgress(),
            rate_limiter=self.limiter,
            uow=FakeUnitOfWork(self.events),
            clock=FixedClock(),
        )

    async def answer(self, wish_id: UUID, user_id: UUID = OWNER, answers: Answers = ANSWERS):
        return await self.answer_panel(
            AnswerPanelCommand(user_id=user_id, wish_id=wish_id, answers=answers)
        )


def shown_wish() -> Wish:
    wish = Wish.create(OWNER, "A week in Lisbon", CREATED)
    wish.show_panel(Destination("Portugal", "Lisbon"), PANEL, CREATED)
    return wish


async def test_the_owner_answers_and_the_wish_is_planned_saved_then_committed():
    wish = shown_wish()
    setup = Setup(wish)

    result = await setup.answer(wish.id)

    assert result == AnswerPanelResult(wish=wish, plan=setup.planner.proposed[0])
    assert result.wish.status is WishStatus.PLANNED
    assert result.wish.answers == ANSWERS
    assert result.wish.updated_at == NOW
    assert setup.wishes.saved == [wish]
    assert setup.events == ["propose", "save", "commit"]


async def test_the_planner_gets_the_answered_wish():
    wish = shown_wish()
    setup = Setup(wish)

    await setup.answer(wish.id)

    assert setup.planner.statuses == [WishStatus.ANSWERED]


async def test_the_result_carries_the_proposed_plan_for_the_wish():
    wish = shown_wish()
    setup = Setup(wish)

    result = await setup.answer(wish.id)

    assert result.plan.wish_id == wish.id
    assert result.plan.status == "proposed"


async def test_when_no_offer_fits_nothing_is_saved_or_committed():
    wish = shown_wish()
    setup = Setup(wish, planner_error=NoOfferFits("no offer fits"))

    with pytest.raises(NoOfferFits):
        await setup.answer(wish.id)
    assert setup.wishes.saved == []
    assert setup.events == ["propose"]


async def test_an_unknown_wish_raises_wish_not_found():
    setup = Setup(shown_wish())

    with pytest.raises(WishNotFound):
        await setup.answer(uuid4())
    assert setup.events == []


async def test_another_users_wish_raises_wish_not_found_and_is_left_untouched():
    wish = shown_wish()
    setup = Setup(wish)

    with pytest.raises(WishNotFound):
        await setup.answer(wish.id, user_id=OTHER)
    assert wish.status is WishStatus.PANEL_SHOWN
    assert setup.events == []


async def test_wish_not_found_is_a_404_not_found():
    assert issubclass(WishNotFound, NotFound)
    assert WishNotFound.code == "wish_not_found"


async def test_a_tag_not_in_the_panel_is_rejected_and_nothing_is_saved():
    wish = shown_wish()
    setup = Setup(wish)
    answers = Answers(
        selected_tags=(SelectedTag("style", "mountain"),),
        budget_max=Decimal("1500"),
        currency="EUR",
        persons=2,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 9),
    )

    with pytest.raises(InvalidAnswers):
        await setup.answer(wish.id, answers=answers)
    assert setup.events == []


# The departure is checked against the server's day (UTC), with one day of tolerance: the web
# app checks against the client's own day, which can be the day before in UTC-12.


def answers_from(start: date) -> Answers:
    return Answers(
        selected_tags=(),
        budget_max=Decimal("1500"),
        currency="EUR",
        persons=2,
        start_date=start,
        end_date=date(2026, 11, 9),
    )


async def test_a_departure_two_days_ago_is_rejected_and_nothing_is_saved():
    wish = shown_wish()
    setup = Setup(wish)

    with pytest.raises(InvalidAnswers):
        await setup.answer(wish.id, answers=answers_from(date(2026, 10, 17)))
    assert setup.events == []  # no model run
    assert wish.status is WishStatus.PANEL_SHOWN


@pytest.mark.parametrize(
    "start",
    [date(2026, 10, 19), date(2026, 10, 18)],
    ids=["today", "yesterday in UTC, today in UTC-12"],
)
async def test_a_departure_today_is_accepted(start):
    wish = shown_wish()
    setup = Setup(wish)

    result = await setup.answer(wish.id, answers=answers_from(start))

    assert result.wish.status is WishStatus.PLANNED


async def test_answering_twice_raises_invalid_transition():
    wish = shown_wish()
    setup = Setup(wish)
    await setup.answer(wish.id)

    with pytest.raises(InvalidTransition):
        await setup.answer(wish.id)
    assert setup.events == ["propose", "save", "commit"]


# A second answer while the first is being planned


class SlowPlanner(FakePlanner):
    """Waits until released, so a second answer arrives while the plan is being built."""

    def __init__(self, events: list[str]) -> None:
        super().__init__(events)
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def propose(self, wish: Wish) -> ProposedPlan:
        self.entered.set()
        await self.release.wait()
        return await super().propose(wish)


async def test_a_second_answer_while_the_plan_is_built_gets_409_without_a_model_run():
    setup = Setup(shown_wish())
    wish_id = next(iter(setup.wishes.by_id))
    slow = SlowPlanner(setup.events)
    setup.answer_panel._planner = slow
    first = asyncio.create_task(setup.answer(wish_id))
    await slow.entered.wait()

    with pytest.raises(AnswerInProgress) as raised:
        await setup.answer(wish_id)

    slow.release.set()
    result = await first
    assert result.wish.status is WishStatus.PLANNED
    assert len(slow.proposed) == 1
    assert raised.value.code == "answer_in_progress"
    assert isinstance(raised.value, Conflict)  # 409


async def test_the_wish_can_be_answered_again_after_a_failed_answer():
    wish = shown_wish()
    setup = Setup(wish, planner_error=NoOfferFits("no offer fits"))
    with pytest.raises(NoOfferFits):
        await setup.answer(wish.id)
    wish.status, wish.answers = WishStatus.PANEL_SHOWN, None  # nothing was saved
    setup.planner.error = None

    result = await setup.answer(wish.id)

    assert result.wish.status is WishStatus.PLANNED


class PlannedMeanwhile(InMemoryAnswersInProgress):
    """Another request plans the wish and lets go of it just before this one holds it."""

    def __init__(self, wishes: FakeWishes, wish_id: UUID) -> None:
        super().__init__()
        self.wishes = wishes
        self.wish_id = wish_id

    def hold(self, wish_id: UUID):
        planned = shown_wish()
        planned.id = self.wish_id
        planned.answer(ANSWERS, NOW)
        planned.mark_planned(NOW)
        self.wishes.by_id[self.wish_id] = planned
        return super().hold(wish_id)


async def test_a_wish_planned_while_waiting_for_the_hold_is_not_planned_again():
    wish = shown_wish()
    setup = Setup(wish)
    setup.answer_panel._in_progress = PlannedMeanwhile(setup.wishes, wish.id)

    with pytest.raises(InvalidTransition):
        await setup.answer(wish.id)

    assert setup.events == []  # no model run, nothing saved


# Rate limit


async def test_a_client_answers_the_limit_then_gets_too_many_requests_before_any_model_call():
    wishes = [shown_wish() for _ in range(ANSWER_LIMIT + 1)]
    setup = Setup(*wishes)
    for wish in wishes[:ANSWER_LIMIT]:
        await setup.answer(wish.id)
    setup.events.clear()

    with pytest.raises(TooManyRequests) as error:
        await setup.answer(wishes[-1].id)

    assert error.value.code == "too_many_requests"
    assert error.value.retry_after_seconds == ANSWER_WINDOW.total_seconds()
    assert setup.events == []  # no plan, no save
    assert wishes[-1].status is WishStatus.PANEL_SHOWN


async def test_rejected_answers_count_toward_the_limit():
    setup = Setup()
    for _ in range(ANSWER_LIMIT):
        with pytest.raises(WishNotFound):
            await setup.answer(uuid4())

    with pytest.raises(TooManyRequests):
        await setup.answer(uuid4())


async def test_the_answer_limit_is_per_client():
    setup = Setup()
    for _ in range(ANSWER_LIMIT):
        with pytest.raises(WishNotFound):
            await setup.answer(uuid4())
    theirs = Wish.create(OTHER, "A week in Lisbon", CREATED)
    theirs.show_panel(Destination("Portugal", "Lisbon"), PANEL, CREATED)
    setup.wishes.by_id[theirs.id] = theirs

    result = await setup.answer(theirs.id, user_id=OTHER)

    assert result.wish.status is WishStatus.PLANNED


async def test_the_answer_limit_resets_after_the_window():
    wish = shown_wish()
    setup = Setup(wish)
    for _ in range(ANSWER_LIMIT):
        with pytest.raises(WishNotFound):
            await setup.answer(uuid4())
    setup.limiter_clock.advance(ANSWER_WINDOW)

    result = await setup.answer(wish.id)

    assert result.wish.status is WishStatus.PLANNED
