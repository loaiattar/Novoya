"""planning.public.delete_for_user against a real PostgreSQL: the plans of the user's wishes
go with their items and extras, the plans of other users stay.

Uses the fixtures of test_planning_repository_sql.py: skipped when Postgres does not answer.
"""

from uuid import UUID, uuid4

from sqlalchemy import func, select

from novoya_api.accounts.infrastructure.db.models import UserModel
from novoya_api.catalog.infrastructure.db.models import ExtraRow
from novoya_api.planning import public as planning_public
from novoya_api.planning.domain.plan import DraftItem, Plan, PlanExtra
from novoya_api.planning.infrastructure.db.models import PlanExtraModel, PlanItemModel, PlanModel
from novoya_api.planning.infrastructure.db.repository import SqlPlanRepository
from novoya_api.wishes.domain.wish import Wish
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from tests.test_planning_repository_sql import (  # noqa: F401  (fixtures)
    NOW,
    add_plan,
    database_url,
    engine,
    new_session,
    offer_ids,
)


async def add_user_with_wish(db) -> tuple[UUID, UUID]:
    """A user and one wish of theirs: (user_id, wish_id)."""
    async with new_session(db) as session:
        user = UserModel(id=uuid4(), email=f"{uuid4()}@example.com", created_at=NOW)
        session.add(user)
        await session.flush()
        wish = Wish.create(user.id, "A week in Chania", NOW)
        await SqlWishRepository(session).add(wish)
        await session.commit()
        return user.id, wish.id


async def add_requested_plan(db, wish_id: UUID, offers) -> Plan:
    """A plan with two items and one extra: asking for the quote writes the extra."""
    hotel, boat = offers
    extra = ExtraRow(
        id=uuid4(),
        category="activity",
        label="Private guide",
        description="A guide for the group",
        pricing="on_quote",
        supplement_eur=None,
        unit="per activity",
        constraints=[],
        active=True,
    )
    async with new_session(db) as session:
        session.add(extra)
        await session.commit()
    plan = Plan.propose(
        wish_id,
        True,
        "Sun and sea",
        [DraftItem(hotel, 1, 7, None), DraftItem(boat, 3, 2, None)],
        8,
        NOW,
    )
    await add_plan(db, plan)
    async with new_session(db) as session:
        plans = SqlPlanRepository(session)
        stored = await plans.get(plan.id)
        stored.request_quote(NOW, [PlanExtra(extra.id, "on_quote", None, label="Private guide")])
        await plans.save(stored)
        await session.commit()
    return plan


async def count_rows(db, model) -> int:
    async with new_session(db) as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_delete_for_user_erases_their_plans_items_and_extras_only(engine, offer_ids):  # noqa: F811
    leaving, leaving_wish = await add_user_with_wish(engine)
    _, staying_wish = await add_user_with_wish(engine)
    await add_requested_plan(engine, leaving_wish, offer_ids)
    kept = await add_requested_plan(engine, staying_wish, offer_ids)

    async with new_session(engine) as session:
        await planning_public.delete_for_user(leaving, session=session)
        await session.commit()

    assert await count_rows(engine, PlanModel) == 1
    assert await count_rows(engine, PlanItemModel) == 2
    assert await count_rows(engine, PlanExtraModel) == 1
    async with new_session(engine) as session:
        assert await session.scalar(select(PlanModel.id)) == kept.id


async def test_delete_for_a_user_without_wishes_erases_nothing(engine, offer_ids):  # noqa: F811
    _, wish_id = await add_user_with_wish(engine)
    await add_requested_plan(engine, wish_id, offer_ids)

    async with new_session(engine) as session:
        await planning_public.delete_for_user(uuid4(), session=session)
        await session.commit()

    assert await count_rows(engine, PlanModel) == 1
    assert await count_rows(engine, PlanItemModel) == 2
    assert await count_rows(engine, PlanExtraModel) == 1
