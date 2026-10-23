"""The advisor profiles (#167) against a real PostgreSQL.

Uses the database fixtures of test_sql.py: skipped when Postgres does not answer.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.domain.advisor_profile import AdvisorProfile, AdvisorService
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import User, UserStatus
from novoya_api.accounts.infrastructure.db.repositories import (
    SqlAdvisorProfileRepository,
    SqlUserRepository,
)
from tests.accounts.fakes import FrozenClock, make_user
from tests.accounts.test_sql import database_url, session  # noqa: F401  (fixtures)

NOW = FrozenClock().now()


async def add_agent(
    db: AsyncSession, email: str, name: str, *, shown: bool = True
) -> tuple[User, AdvisorProfile]:
    user = make_user(email, role=Role.AGENT)
    await SqlUserRepository(db).add(user)
    profile = AdvisorProfile.new(user.id, NOW)
    profile.edit(
        public_name=name,
        title="Conseiller voyage",
        summary=None,
        services=[AdvisorService("Grèce", "Greece"), AdvisorService(None, "Trains")],
        consent=True,
        shown=shown,
        by=user.id,
        now=NOW,
    )
    await SqlAdvisorProfileRepository(db).save(profile)
    await db.commit()
    return user, profile


async def test_a_profile_is_saved_and_read_back_with_its_services(session):  # noqa: F811
    user, profile = await add_agent(session, "camille@x.io", "Camille")
    profile.edit(
        public_name="Cam",
        title=None,
        summary="Toujours à la recherche de la prochaine pépite.",
        services=[AdvisorService("Maroc", None)],
        consent=True,
        shown=True,
        by=user.id,
        now=NOW,
    )
    await SqlAdvisorProfileRepository(session).save(profile)
    await session.commit()

    read = await SqlAdvisorProfileRepository(session).get_for_user(user.id)
    assert read == profile
    by_user = await SqlAdvisorProfileRepository(session).for_users([user.id])
    assert by_user == {user.id: profile}


async def test_only_shown_active_agents_are_listed_by_name(session):  # noqa: F811
    users = SqlUserRepository(session)
    await add_agent(session, "zoe@x.io", "Zoé")
    await add_agent(session, "anna@x.io", "Anna")
    await add_agent(session, "hidden@x.io", "Hidden", shown=False)
    demoted, _ = await add_agent(session, "demoted@x.io", "Demoted")
    disabled, _ = await add_agent(session, "disabled@x.io", "Disabled")
    demoted.role = Role.CLIENT
    disabled.status = UserStatus.DISABLED
    await users.save(demoted)
    await users.save(disabled)
    await session.commit()

    shown = await SqlAdvisorProfileRepository(session).list_shown()

    assert [p.public_name for p in shown] == ["Anna", "Zoé"]


async def test_the_profile_goes_with_the_account(session):  # noqa: F811
    user, _ = await add_agent(session, "camille@x.io", "Camille")
    await SqlUserRepository(session).delete(user.id)
    await session.commit()

    assert await SqlAdvisorProfileRepository(session).get_for_user(user.id) is None
    assert await SqlAdvisorProfileRepository(session).list_shown() == []
