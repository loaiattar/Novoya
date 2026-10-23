"""wishes.public.wishes_for_user against PostgreSQL. Skipped when Postgres does not answer."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from novoya_api.accounts.infrastructure.db.models import UserModel
from novoya_api.wishes import public as wishes_public
from novoya_api.wishes.domain.wish import Wish
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository
from tests.test_catalog_sql import database_url  # noqa: F401  (fixture)
from tests.test_planning_repository_sql import engine, new_session  # noqa: F401

NOW = datetime(2026, 4, 19, 9, 0, tzinfo=UTC)


async def add_user(session) -> UserModel:
    user = UserModel(id=uuid4(), email=f"{uuid4()}@example.com", created_at=NOW)
    session.add(user)
    await session.flush()
    return user


async def test_wishes_for_user_lists_the_newest_first(engine):  # noqa: F811
    async with new_session(engine) as session:
        user = await add_user(session)
        repository = SqlWishRepository(session)
        await repository.add(Wish.create(user.id, "Oldest", NOW))
        await repository.add(Wish.create(user.id, "Newest", NOW + timedelta(hours=2)))
        await repository.add(Wish.create(user.id, "Middle", NOW + timedelta(hours=1)))
        await session.commit()

        wishes = await wishes_public.wishes_for_user(user.id, session=session)

        assert [wish.text for wish in wishes] == ["Newest", "Middle", "Oldest"]
        assert all(wish.status == "draft" for wish in wishes)
        assert wishes[0].country is None
        assert wishes[0].persons is None


async def test_wishes_for_user_leaves_other_users_out(engine):  # noqa: F811
    async with new_session(engine) as session:
        mine = await add_user(session)
        other = await add_user(session)
        repository = SqlWishRepository(session)
        await repository.add(Wish.create(mine.id, "Mine", NOW))
        await repository.add(Wish.create(other.id, "Not mine", NOW))
        await session.commit()

        wishes = await wishes_public.wishes_for_user(mine.id, session=session)

        assert [wish.text for wish in wishes] == ["Mine"]


async def test_a_user_without_wishes_gets_an_empty_list(engine):  # noqa: F811
    async with new_session(engine) as session:
        user = await add_user(session)
        await session.commit()

        assert await wishes_public.wishes_for_user(user.id, session=session) == []
