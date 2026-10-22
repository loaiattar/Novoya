"""accounts.public.get_user against a real PostgreSQL: what other modules read of a user.

Uses the database fixtures of test_sql.py: skipped when Postgres does not answer.
"""

from uuid import uuid4

from novoya_api.accounts.domain.user import User
from novoya_api.accounts.domain.value_objects import Email
from novoya_api.accounts.infrastructure.db.repositories import SqlUserRepository
from novoya_api.accounts.public import UserView, get_user
from novoya_api.shared.domain.value_objects import Locale
from tests.accounts.fakes import FrozenClock
from tests.accounts.test_sql import database_url, session  # noqa: F401  (fixtures)

NOW = FrozenClock().now()


async def test_get_user_returns_the_users_name_email_and_language(session):  # noqa: F811
    user = User.register(Email("alice@example.com"), "Alice", "Martin", Locale.FR, NOW)
    await SqlUserRepository(session).add(user)
    await session.commit()

    view = await get_user(user.id.value, session=session)

    assert view == UserView(user.id.value, "alice@example.com", "Alice Martin", Locale.FR)


async def test_get_user_returns_none_for_an_unknown_user(session):  # noqa: F811
    assert await get_user(uuid4(), session=session) is None
