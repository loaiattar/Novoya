"""AnswerPanel with the real planner and repositories on one session, against PostgreSQL.

The planner ends the read before the model runs, so this checks that the plan and the
planned wish are still committed together, and that nothing is kept when no offer fits.
Skipped when Postgres does not answer. The model is replaced by NoModelPlanWriter.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from novoya_api.accounts.infrastructure.db.models import UserModel
from novoya_api.planning import public as planning_public
from novoya_api.planning.domain.errors import NoOfferFits
from novoya_api.planning.infrastructure.db.models import PlanItemModel, PlanModel
from novoya_api.planning.infrastructure.llm.plan_writer import LlmPlanWriter, NoModelPlanWriter
from novoya_api.planning.infrastructure.llm.tools import TripBounds
from novoya_api.shared.domain.errors import InvalidTransition
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from novoya_api.wishes.application.use_cases.answer_panel import (
    AnswerPanel,
    AnswerPanelCommand,
)
from novoya_api.wishes.domain.answers import Answers, SelectedTag
from novoya_api.wishes.domain.panel import Panel
from novoya_api.wishes.domain.wish import Destination, Wish, WishStatus
from novoya_api.wishes.infrastructure.answers_in_progress import InMemoryAnswersInProgress
from novoya_api.wishes.infrastructure.db.models import WishModel
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from novoya_api.wishes.infrastructure.planner import PartnerPlanner
from tests.accounts.fakes import NoopRateLimiter
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_planning_repository_sql import engine, new_session, offer_ids  # noqa: F401

NOW = datetime(2026, 4, 19, 9, 0, tzinfo=UTC)  # before the trip: a past departure is refused
REAL_WRITER = planning_public._writer  # kept before the autouse fixture replaces it


class FixedClock:
    def now(self) -> datetime:
        return NOW


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    monkeypatch.setattr(planning_public, "_writer", NoModelPlanWriter)


@pytest.fixture
async def shown_wish(engine) -> Wish:  # noqa: F811
    async with new_session(engine) as session:
        user = UserModel(id=uuid4(), email=f"{uuid4()}@example.com", created_at=NOW)
        session.add(user)
        await session.flush()
        wish = Wish.create(user.id, "A week by the sea in Chania", NOW)
        wish.show_panel(Destination("Greece", "Chania"), Panel.from_tags(["style:beach"]), NOW)
        await SqlWishRepository(session).add(wish)
        await session.commit()
        return wish


def answers(persons: int = 2) -> Answers:
    return Answers(
        selected_tags=(SelectedTag("style", "beach"),),
        budget_max=Decimal("1500"),
        currency="EUR",
        persons=persons,
        start_date=date(2026, 5, 10),
        end_date=date(2026, 5, 17),
    )


async def answer(engine, wish: Wish, persons: int = 2):  # noqa: F811
    async with new_session(engine) as session:
        use_case = AnswerPanel(
            wishes=SqlWishRepository(session),
            planner=PartnerPlanner(session),
            in_progress=InMemoryAnswersInProgress(),
            rate_limiter=NoopRateLimiter(),
            uow=SqlAlchemyUnitOfWork(session),
            clock=FixedClock(),
        )
        return await use_case(AnswerPanelCommand(wish.user_id, wish.id, answers(persons)))


async def stored(engine, wish_id: UUID) -> tuple[str, int, int]:  # noqa: F811
    async with new_session(engine) as session:
        status = await session.scalar(select(WishModel.status).where(WishModel.id == wish_id))
        plans = await session.scalar(
            select(func.count()).select_from(PlanModel).where(PlanModel.wish_id == wish_id)
        )
        items = await session.scalar(select(func.count()).select_from(PlanItemModel))
        return status, plans, items


async def test_the_plan_and_the_planned_wish_are_committed_together(
    engine,  # noqa: F811
    shown_wish,
    offer_ids,  # noqa: F811
):
    hotel, boat = offer_ids

    result = await answer(engine, shown_wish)

    assert result.wish.status is WishStatus.PLANNED
    assert [(i.offer_id, i.day, i.quantity) for i in result.plan.items] == [
        (hotel, 1, 7),
        (boat, 1, 1),
    ]
    assert await stored(engine, shown_wish.id) == ("planned", 1, 2)


async def test_when_no_offer_fits_nothing_is_kept(engine, shown_wish, offer_ids):  # noqa: F811
    with pytest.raises(NoOfferFits):
        await answer(engine, shown_wish, persons=10)  # the offers take at most 4

    assert await stored(engine, shown_wish.id) == ("panel_shown", 0, 0)


class AnswersMeanwhile:
    """A writer that, while 'the model thinks', lets another request plan the same wish."""

    def __init__(self, engine, wish_id: UUID) -> None:  # noqa: F811
        self.engine = engine
        self.wish_id = wish_id

    async def write(self, request):
        async with new_session(self.engine) as other:
            await other.execute(
                update(WishModel).where(WishModel.id == self.wish_id).values(status="planned")
            )
            await other.commit()
        return None  # the fallback builds the plan


async def test_a_wish_changed_during_the_model_run_keeps_no_plan(
    engine,  # noqa: F811
    shown_wish,
    offer_ids,  # noqa: F811
    monkeypatch,
):
    monkeypatch.setattr(planning_public, "_writer", lambda: AnswersMeanwhile(engine, shown_wish.id))

    with pytest.raises(InvalidTransition):
        await answer(engine, shown_wish)

    assert await stored(engine, shown_wish.id) == ("planned", 0, 0)


def test_the_model_reads_the_catalog_in_sessions_of_its_own(monkeypatch):
    calls = []
    monkeypatch.setattr(planning_public, "get_orchestrator", lambda **kwargs: object())
    monkeypatch.setattr(
        planning_public, "travel_tools", lambda *args, **kwargs: calls.append(kwargs) or []
    )

    writer = REAL_WRITER()
    assert isinstance(writer, LlmPlanWriter)
    # The tools are built for each trip (#182): bound to its dates and travellers, and with
    # no session, so the request's connection is free while the model thinks.
    request = planning_public.PlanRequest(
        wish_id=uuid4(),
        text="A calm week",
        country="Greece",
        city="Chania",
        tags=(),
        persons=2,
        start_date=date(2026, 5, 10),
        end_date=date(2026, 5, 17),
        budget_max=Decimal("1500"),
    )
    planning_public._trip_tools(request)

    assert calls == [
        {"trip": TripBounds(persons=2, start_date=date(2026, 5, 10), end_date=date(2026, 5, 17))}
    ]
