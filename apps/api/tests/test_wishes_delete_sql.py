"""Erasing a user's wishes, against PostgreSQL. Skipped when Postgres does not answer."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from novoya_api.accounts.infrastructure.db.models import UserModel
from novoya_api.planning.domain.plan import DraftItem, Plan
from novoya_api.wishes import public as wishes_public
from novoya_api.wishes.domain.wish import Wish
from novoya_api.wishes.infrastructure.db.models import WishModel
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_planning_repository_sql import (  # noqa: F401  (fixtures)
    add_plan,
    engine,
    new_session,
    offer_ids,
)

NOW = datetime(2026, 4, 19, 9, 0, tzinfo=UTC)


async def add_user_with_wishes(session, count: int) -> UserModel:
    user = UserModel(id=uuid4(), email=f"{uuid4()}@example.com", created_at=NOW)
    session.add(user)
    await session.flush()
    for number in range(count):
        await SqlWishRepository(session).add(Wish.create(user.id, f"Wish {number}", NOW))
    await session.flush()
    return user


async def count_wishes(session, user_id: UUID) -> int:
    query = select(func.count()).select_from(WishModel).where(WishModel.user_id == user_id)
    return await session.scalar(query)


async def test_delete_for_user_erases_only_that_users_wishes(engine):  # noqa: F811
    async with new_session(engine) as session:
        leaving = await add_user_with_wishes(session, 2)
        staying = await add_user_with_wishes(session, 1)
        await session.commit()

        await wishes_public.delete_for_user(leaving.id, session=session)
        await session.commit()

        assert await count_wishes(session, leaving.id) == 0
        assert await count_wishes(session, staying.id) == 1


async def test_delete_for_user_fails_while_a_plan_still_points_to_a_wish(engine, offer_ids):  # noqa: F811
    """No cascade from wishes to plans: the plans must be erased first."""
    async with new_session(engine) as session:
        user = await add_user_with_wishes(session, 1)
        await session.commit()
        wish_id = await session.scalar(select(WishModel.id).where(WishModel.user_id == user.id))
    hotel, _ = offer_ids
    plan = Plan.propose(wish_id, True, "Sun and sea", [DraftItem(hotel, 1, 7, None)], 8, NOW)
    await add_plan(engine, plan)

    async with new_session(engine) as session:
        with pytest.raises(IntegrityError):
            await wishes_public.delete_for_user(user.id, session=session)

    async with new_session(engine) as session:
        assert await count_wishes(session, user.id) == 1
