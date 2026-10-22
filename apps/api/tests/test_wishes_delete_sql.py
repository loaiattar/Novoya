"""Erasing a user's wishes, against PostgreSQL. Skipped when Postgres does not answer."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select

from novoya_api.accounts.infrastructure.db.models import UserModel
from novoya_api.wishes import public as wishes_public
from novoya_api.wishes.domain.wish import Wish
from novoya_api.wishes.infrastructure.db.models import WishModel
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_planning_repository_sql import engine, new_session  # noqa: F401

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
