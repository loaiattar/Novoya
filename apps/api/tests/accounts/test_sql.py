"""The SQL repositories, the migration and the grant-role command, against a real PostgreSQL.

Needs the PostgreSQL of docker compose (or the CI service); skipped when it does not answer.
They run in a separate database, novoya_test, created if needed: the migrations are applied
once, then each test starts from empty tables.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from novoya_api.accounts.application.ports.identity_provider import PendingSignIn
from novoya_api.accounts.application.services.one_time_tokens import consume_token
from novoya_api.accounts.application.use_cases.change_user_role import (
    ChangeUserRole,
    ChangeUserRoleCommand,
)
from novoya_api.accounts.domain.auth_session import AuthSession
from novoya_api.accounts.domain.credentials import PasswordCredential
from novoya_api.accounts.domain.errors import (
    EmailAlreadyUsed,
    IdentityAlreadyLinked,
    InvalidOrExpiredToken,
    LastAdminRequired,
)
from novoya_api.accounts.domain.oauth_identity import OAuthIdentity
from novoya_api.accounts.domain.one_time_token import OneTimeToken, TokenPurpose
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import User, UserStatus
from novoya_api.accounts.domain.value_objects import Email, PasswordHash
from novoya_api.accounts.infrastructure.db.repositories import (
    SqlOAuthIdentityRepository,
    SqlOAuthStateStore,
    SqlOneTimeTokenRepository,
    SqlPasswordCredentialRepository,
    SqlRoleChangeRepository,
    SqlSessionRepository,
    SqlUserRepository,
)
from novoya_api.accounts.infrastructure.security import SecureTokenGenerator
from novoya_api.accounts.presentation import cli
from novoya_api.accounts.presentation.http.dependencies import build_store
from novoya_api.config import get_settings
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.shared.infrastructure.db.session import get_engine, get_sessionmaker
from tests.accounts.fakes import FrozenClock, google_identity, make_user

API_DIR = Path(__file__).parent.parent.parent
TABLES = (
    "oauth_states, oauth_identities, role_changes, one_time_tokens, sessions, "
    "password_credentials, users"
)
NOW = FrozenClock().now()


async def database_answers(url: str) -> bool:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def create_test_database(url: str, name: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    async with engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
    await engine.dispose()


def clear_cached_settings() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest.fixture(scope="module")
def database_url() -> Iterator[str]:
    """A separate database, novoya_test, so the tests never empty the development one."""
    dev_url = get_settings().database_url
    if not asyncio.run(database_answers(dev_url)):
        pytest.skip("PostgreSQL is not running (docker compose up db)")
    url = dev_url.rsplit("/", 1)[0] + "/novoya_test"
    asyncio.run(create_test_database(dev_url, "novoya_test"))

    # Everything that reads the settings (Alembic, the grant-role command) uses that database.
    previous = os.environ.get("NOVOYA_DATABASE_URL")
    os.environ["NOVOYA_DATABASE_URL"] = url
    clear_cached_settings()
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    command.upgrade(config, "head")
    yield url

    if previous is None:
        del os.environ["NOVOYA_DATABASE_URL"]
    else:
        os.environ["NOVOYA_DATABASE_URL"] = previous
    clear_cached_settings()


@pytest.fixture
async def session(database_url) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def test_users_have_nullable_first_and_last_name_columns(session):
    rows = (
        await session.execute(
            text(
                """
                SELECT column_name, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name IN ('first_name', 'last_name')
                """
            )
        )
    ).all()
    cols = {row.column_name: row for row in rows}
    assert cols["first_name"].character_maximum_length == 100
    assert cols["first_name"].is_nullable == "YES"
    assert cols["last_name"].character_maximum_length == 100
    assert cols["last_name"].is_nullable == "YES"


async def test_existing_accounts_load_with_empty_first_and_last_name(session):
    await session.execute(
        text(
            """
            INSERT INTO users (id, email, name, role, locale, status, created_at)
            VALUES (:id, :email, :name, 'client', 'en', 'active', :now)
            """
        ),
        {
            "id": uuid4(),
            "email": "old@example.com",
            "name": "Old Name",
            "now": NOW,
        },
    )
    await session.commit()

    user = await SqlUserRepository(session).get_by_email(Email("old@example.com"))
    assert user is not None
    assert user.name == "Old Name"
    assert user.first_name is None
    assert user.last_name is None


async def test_register_with_max_length_names_fits_in_the_name_column(session):
    first, last = "A" * 100, "B" * 100
    user = User.register(Email("long@example.com"), first, last, Locale.EN, NOW)
    await SqlUserRepository(session).add(user)
    await session.commit()

    stored = await SqlUserRepository(session).get(user.id)
    assert stored is not None
    assert stored.first_name == first
    assert stored.last_name == last
    assert stored.name == (first + " " + last)[:200]
    assert len(stored.name) == 200


async def test_admin_search_matches_first_and_last_name(session):
    users = SqlUserRepository(session)
    await users.add(make_user("a@x.io"))
    await session.commit()

    assert [u.email.value for u in await users.search("ALICE", None, 10, 0)] == ["a@x.io"]
    assert [u.email.value for u in await users.search("martin", None, 10, 0)] == ["a@x.io"]


def test_first_and_last_name_migration_backfills_and_downgrades(database_url):
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    user_id = uuid4()

    async def run(sql: str, params: dict | None = None):
        engine = create_async_engine(database_url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                result = await connection.execute(text(sql), params or {})
                if result.returns_rows:
                    return result.mappings().all()
                return []
        finally:
            await engine.dispose()

    asyncio.run(run(f"TRUNCATE {TABLES} CASCADE"))
    command.downgrade(config, "58aa3536140b")
    asyncio.run(
        run(
            """
            INSERT INTO users (id, email, name, role, locale, status, created_at)
            VALUES (:id, 'old@example.com', 'Ali B.', 'client', 'en', 'active', :now)
            """,
            {"id": user_id, "now": NOW},
        )
    )
    command.upgrade(config, "head")
    [row] = asyncio.run(
        run("SELECT name, first_name, last_name FROM users WHERE email = 'old@example.com'")
    )
    assert (row["name"], row["first_name"], row["last_name"]) == ("Ali B.", "Ali", "B.")

    command.downgrade(config, "58aa3536140b")
    columns = asyncio.run(
        run(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users' AND column_name IN ('first_name', 'last_name')
            """
        )
    )
    assert columns == []
    [kept] = asyncio.run(run("SELECT name FROM users WHERE email = 'old@example.com'"))
    assert kept["name"] == "Ali B."

    command.upgrade(config, "head")
    asyncio.run(run(f"TRUNCATE {TABLES} CASCADE"))


async def test_users_are_stored_and_found_by_email(session):
    users = SqlUserRepository(session)
    alice = make_user("alice@example.com")
    await users.add(alice)
    await session.commit()

    found = await users.get_by_email(Email("ALICE@example.com"))
    assert found == alice
    assert await users.get(alice.id) == alice


async def test_a_changed_language_is_saved(session):
    users = SqlUserRepository(session)
    await users.add(make_user("alice@example.com"))
    await session.commit()

    alice = await users.get_by_email(Email("alice@example.com"))
    alice.change_locale(Locale.FR)
    await users.save(alice)
    await session.commit()

    row = (await session.execute(text("SELECT locale FROM users"))).one()
    assert row.locale == "fr"


async def test_the_database_refuses_a_second_account_with_the_same_email(session):
    users = SqlUserRepository(session)
    await users.add(make_user("alice@example.com"))
    with pytest.raises(EmailAlreadyUsed):
        await users.add(make_user("alice@example.com"))


async def test_users_are_saved_counted_and_searched(session):
    users = SqlUserRepository(session)
    admin = make_user("admin@x.io", role=Role.ADMIN, now=NOW)
    agent = make_user("agent@x.io", now=NOW + timedelta(minutes=1))
    await users.add(admin)
    await users.add(agent)
    agent.change_role(Role.AGENT, changed_by=admin.id, now=NOW)
    await users.save(agent)
    await session.commit()

    assert await users.count_active_with_role(Role.ADMIN) == 1
    assert [u.email.value for u in await users.search(None, None, 10, 0)] == [
        "agent@x.io",
        "admin@x.io",
    ]
    assert [u.email.value for u in await users.search("AGENT", None, 10, 0)] == ["agent@x.io"]
    assert [u.email.value for u in await users.search(None, Role.ADMIN, 10, 0)] == ["admin@x.io"]


async def test_role_changes_are_logged_with_their_source(session):
    users, changes = SqlUserRepository(session), SqlRoleChangeRepository(session)
    user = make_user()
    await users.add(user)
    await changes.add(user.change_role(Role.ADMIN, changed_by=None, now=NOW))
    await session.commit()

    row = (await session.execute(text("SELECT source, changed_by FROM role_changes"))).one()
    assert tuple(row) == ("cmd_grant_role", None)


async def test_status_change_is_kept_and_survives_the_admin(session):
    users = SqlUserRepository(session)
    admin = make_user("admin@x.io", role=Role.ADMIN, now=NOW)
    client = make_user("client@x.io", now=NOW)
    await users.add(admin)
    await users.add(client)
    client.change_status(UserStatus.DISABLED, changed_by=admin.id, now=NOW)
    await users.save(client)
    await session.commit()

    stored = await SqlUserRepository(session).get(client.id)
    assert not stored.is_active
    assert (stored.status_changed_by, stored.status_changed_at) == (admin.id, NOW)

    # Deleting the admin keeps the change, without its author.
    await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": admin.id.value})
    await session.commit()
    session.expire_all()
    stored = await SqlUserRepository(session).get(client.id)
    assert (stored.status_changed_by, stored.status_changed_at) == (None, NOW)


async def test_password_credentials_are_upserted(session):
    users, credentials = SqlUserRepository(session), SqlPasswordCredentialRepository(session)
    user = make_user()
    await users.add(user)
    await credentials.upsert(PasswordCredential(user.id, PasswordHash("first"), NOW))
    await credentials.upsert(PasswordCredential(user.id, PasswordHash("second"), NOW))
    await session.commit()
    assert (await credentials.get(user.id)).password_hash == PasswordHash("second")


async def test_sessions_come_with_their_user_and_are_revoked(session):
    users, sessions = SqlUserRepository(session), SqlSessionRepository(session)
    user = make_user()
    await users.add(user)
    ttl = timedelta(days=7), timedelta(days=30)
    kept = AuthSession.open(user.id, "a" * 64, NOW, *ttl, user_agent="laptop")
    other = AuthSession.open(user.id, "b" * 64, NOW, *ttl, user_agent="phone")
    await sessions.add(kept)
    await sessions.add(other)
    await session.commit()

    found_session, found_user = await sessions.get_with_user("a" * 64)
    assert found_session.id == kept.id
    assert found_user.email == user.email

    await sessions.revoke_all_for_user(user.id, NOW, except_session_id=kept.id)
    await session.commit()
    assert (await sessions.get("a" * 64)).revoked_at is None
    assert (await sessions.get("b" * 64)).revoked_at == NOW


async def test_one_time_tokens_are_invalidated(session):
    users, tokens = SqlUserRepository(session), SqlOneTimeTokenRepository(session)
    user = make_user()
    await users.add(user)
    token = OneTimeToken.issue(user.id, TokenPurpose.PASSWORD_RESET, "c" * 64, NOW)
    await tokens.add(token)
    await session.commit()

    assert await tokens.get("c" * 64, TokenPurpose.EMAIL_VERIFICATION) is None
    await tokens.invalidate_all(user.id, TokenPurpose.PASSWORD_RESET, NOW)
    await session.commit()
    assert (await tokens.get("c" * 64, TokenPurpose.PASSWORD_RESET)).used_at == NOW


def test_grant_role_command(database_url, capsys):
    async def add_user() -> None:
        engine = create_async_engine(database_url, poolclass=NullPool)
        async with engine.begin() as connection:
            await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
        async with async_sessionmaker(engine)() as session:
            await SqlUserRepository(session).add(make_user("boss@x.io"))
            await session.commit()
        await engine.dispose()

    asyncio.run(add_user())
    assert cli.main(["grant-role", "--email", "boss@x.io", "--role", "admin"]) == 0
    assert "boss@x.io is now admin" in capsys.readouterr().out
    assert cli.main(["grant-role", "--email", "nobody@x.io", "--role", "admin"]) == 1
    assert "user_not_found" in capsys.readouterr().err


async def test_password_credentials_are_deleted(session):
    users, credentials = SqlUserRepository(session), SqlPasswordCredentialRepository(session)
    alice = make_user("alice@example.com")
    await users.add(alice)
    await credentials.upsert(PasswordCredential(alice.id, PasswordHash("h"), NOW))
    await session.commit()

    await credentials.delete(alice.id)
    await session.commit()

    assert await credentials.get(alice.id) is None


async def test_oauth_identities_are_found_by_provider_and_subject(session):
    users, identities = SqlUserRepository(session), SqlOAuthIdentityRepository(session)
    alice = make_user("alice@example.com")
    await users.add(alice)
    identity = OAuthIdentity.link(alice.id, google_identity(), NOW)
    await identities.add(identity)
    await session.commit()

    found = await identities.get("google", "google-sub-1")
    assert found == identity
    assert await identities.get("google", "another-sub") is None
    assert await identities.providers_for_user(alice.id) == {"google"}
    assert await identities.providers_for_user(make_user("bob@example.com").id) == set()

    found.touch(NOW + timedelta(days=1))
    await identities.save(found)
    await session.commit()
    assert (await identities.get("google", "google-sub-1")).last_login_at == NOW + timedelta(days=1)


async def test_a_google_account_is_linked_to_one_user_only(session):
    users, identities = SqlUserRepository(session), SqlOAuthIdentityRepository(session)
    alice, bob = make_user("alice@example.com"), make_user("bob@example.com")
    await users.add(alice)
    await users.add(bob)
    await identities.add(OAuthIdentity.link(alice.id, google_identity(), NOW))

    with pytest.raises(IdentityAlreadyLinked):
        await identities.add(OAuthIdentity.link(bob.id, google_identity(), NOW))


async def test_a_user_has_at_most_one_google_account(session):
    users, identities = SqlUserRepository(session), SqlOAuthIdentityRepository(session)
    alice = make_user("alice@example.com")
    await users.add(alice)
    await identities.add(OAuthIdentity.link(alice.id, google_identity(), NOW))

    with pytest.raises(IdentityAlreadyLinked):
        await identities.add(
            OAuthIdentity.link(alice.id, google_identity(subject="another-google-account"), NOW)
        )


async def test_an_identity_for_a_missing_user_is_not_reported_as_already_linked(session):
    """Only the (provider, subject) unique index means "already linked"; a foreign key
    failure is a bug and must surface as it is."""
    from sqlalchemy.exc import IntegrityError

    ghost = make_user("ghost@example.com")  # never added

    with pytest.raises(IntegrityError):
        await SqlOAuthIdentityRepository(session).add(
            OAuthIdentity.link(ghost.id, google_identity(), NOW)
        )


PENDING = PendingSignIn("google", "verifier", "nonce", "/wishes/new")


async def test_an_oauth_state_is_read_once(session):
    states = SqlOAuthStateStore(session)
    await states.put("a" * 64, PENDING, NOW + timedelta(minutes=10), NOW)
    await session.commit()

    assert await states.pop("a" * 64, NOW) == PENDING
    await session.commit()
    assert await states.pop("a" * 64, NOW) is None


async def test_an_expired_oauth_state_is_not_returned_and_is_cleaned_up(session):
    states = SqlOAuthStateStore(session)
    later = NOW + timedelta(minutes=11)
    await states.put("a" * 64, PENDING, NOW + timedelta(minutes=10), NOW)
    await session.commit()

    assert await states.pop("a" * 64, later) is None

    await states.put("b" * 64, PENDING, later + timedelta(minutes=10), later)  # cleans "a"
    await session.commit()
    count = await session.scalar(text("SELECT count(*) FROM oauth_states"))
    assert count == 1


# Two requests at the same time: two sessions, the second must wait for the first.


@pytest.fixture
async def sessions(database_url) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def blocked(task: asyncio.Task) -> bool:
    await asyncio.sleep(0.3)
    return not task.done()


async def test_two_demotions_at_once_keep_one_admin(sessions):
    a = make_user("a@x.io", role=Role.ADMIN)
    b = make_user("b@x.io", role=Role.ADMIN)
    async with sessions() as setup:
        store = build_store(setup)
        await store.users.add(a)
        await store.users.add(b)
        await setup.commit()

    async with sessions() as first, sessions() as second:
        users = SqlUserRepository(first)
        assert await users.count_active_with_role(Role.ADMIN) == 2  # A's request, admins locked
        store = build_store(second)
        demote_a = ChangeUserRole(store.users, store.role_changes, store.uow, FrozenClock())
        b_demotes_a = asyncio.create_task(
            demote_a(ChangeUserRoleCommand(a.id, Role.CLIENT, changed_by=None))
        )
        assert await blocked(b_demotes_a)

        target = await users.get(b.id)
        target.change_role(Role.CLIENT, changed_by=None, now=NOW)
        await users.save(target)
        await first.commit()

        with pytest.raises(LastAdminRequired):
            await b_demotes_a


async def test_a_reset_link_used_by_two_requests_at_once_works_once(sessions):
    generator = SecureTokenGenerator()
    raw = generator.generate()
    alice = make_user("alice@example.com")
    async with sessions() as setup:
        store = build_store(setup)
        await store.users.add(alice)
        await store.tokens.add(
            OneTimeToken.issue(alice.id, TokenPurpose.PASSWORD_RESET, generator.hash(raw), NOW)
        )
        await setup.commit()

    async with sessions() as first, sessions() as second:
        purpose = TokenPurpose.PASSWORD_RESET
        await consume_token(SqlOneTimeTokenRepository(first), generator, raw, purpose, NOW)
        again = asyncio.create_task(
            consume_token(SqlOneTimeTokenRepository(second), generator, raw, purpose, NOW)
        )
        assert await blocked(again)
        await first.commit()

        with pytest.raises(InvalidOrExpiredToken):
            await again


async def test_a_state_sent_back_twice_at_once_signs_in_once(sessions):
    async with sessions() as setup:
        await SqlOAuthStateStore(setup).put("a" * 64, PENDING, NOW + timedelta(minutes=10), NOW)
        await setup.commit()

    async def pop() -> PendingSignIn | None:
        async with sessions() as session:
            pending = await SqlOAuthStateStore(session).pop("a" * 64, NOW)
            await asyncio.sleep(0.2)  # hold the row until commit
            await session.commit()
            return pending

    results = await asyncio.gather(pop(), pop())

    assert sorted(results, key=lambda r: r is None) == [PENDING, None]


async def test_a_failed_google_sign_in_changes_nothing_but_the_used_state(session):
    """A disabled, unverified account: SignIn deletes its password and revokes its sessions
    (pre-hijacking guard), then the session opener refuses the disabled account. The request
    ends without commit, like get_session does: the account must be as it was."""
    from novoya_api.accounts.application.dto import ClientInfo
    from novoya_api.accounts.application.services.session_opener import (
        SessionOpener,
        SessionPolicy,
    )
    from novoya_api.accounts.application.use_cases.sign_in import SignIn, SignInCommand
    from novoya_api.accounts.domain.errors import AccountDisabled
    from novoya_api.accounts.infrastructure.identity_providers import DictIdentityProviders
    from tests.accounts.fakes import FakeIdentityProvider

    store = build_store(session)
    tokens = SecureTokenGenerator()
    squatter = make_user("alice@example.com", verified=False, status=UserStatus.DISABLED)
    await store.users.add(squatter)
    await store.credentials.upsert(PasswordCredential(squatter.id, PasswordHash("h"), NOW))
    await store.oauth_states.put(
        tokens.hash("the-state"), PENDING, NOW + timedelta(minutes=10), NOW
    )
    await session.commit()
    provider = FakeIdentityProvider()
    clock = FrozenClock(NOW)
    sign_in = SignIn(
        DictIdentityProviders([provider]),
        store.oauth_states,
        tokens,
        store.users,
        store.identities,
        store.credentials,
        store.sessions,
        SessionOpener(store.sessions, tokens, clock, SessionPolicy()),
        store.uow,
        clock,
    )
    client = ClientInfo("127.0.0.1", "tests", None)

    with pytest.raises(AccountDisabled):
        await sign_in(
            SignInCommand("google", "code", "the-state", "http://cb", None, client, "the-state")
        )
    await session.rollback()

    assert await store.credentials.get(squatter.id) is not None
    assert not (await store.users.get(squatter.id)).is_email_verified
    assert await store.identities.providers_for_user(squatter.id) == set()
    assert await store.oauth_states.pop(tokens.hash("the-state"), NOW) is None  # used up


async def test_a_sign_in_does_not_undo_a_role_change_made_meanwhile(sessions):
    """Copilot's scenario on #73: the sign-in reads the user, an admin demotes them and
    commits, then the sign-in saves the user. Only the changed columns are written, so the
    demotion stays."""
    async with sessions() as setup:
        agent = make_user("alice@example.com", role=Role.AGENT, verified=False)
        await SqlUserRepository(setup).add(agent)
        await setup.commit()

    async with sessions() as signing_in:
        users = SqlUserRepository(signing_in)
        user = await users.get(agent.id)  # the sign-in has read the agent

        async with sessions() as admin:  # the demotion commits in between
            await admin.execute(
                text("UPDATE users SET role = 'client' WHERE id = :id"), {"id": agent.id.value}
            )
            await admin.commit()

        user.verify_email(NOW)
        user.fill_in_name("Alice Martin")
        await users.save(user)
        await signing_in.commit()

    async with sessions() as check:
        stored = await SqlUserRepository(check).get(agent.id)
    assert stored.role is Role.CLIENT
    assert stored.is_email_verified
