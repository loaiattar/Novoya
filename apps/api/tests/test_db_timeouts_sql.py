"""Database timeouts against a real PostgreSQL (novoya_test, like test_catalog_sql.py).

Skipped when Postgres does not answer. No fixed sleeps: each wait has a short timeout, and
asyncio.timeout turns a timeout that is not applied into a failure instead of a hang.
"""

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.pool import NullPool

from alembic import command
from novoya_api.catalog.infrastructure.db.models import PartnerRow
from novoya_api.config import Settings, get_settings
from novoya_api.main import create_app
from novoya_api.shared.infrastructure.db.session import build_engine
from novoya_api.shared.presentation.http.errors import (
    DATABASE_BUSY_RETRY_AFTER_SECONDS,
    handle_database_error,
)
from tests.test_catalog_sql import (
    API_DIR,
    database_url,  # noqa: F401  (fixture)
)

# Long enough for any timeout under test to fire, short enough that a regression fails fast.
GUARD_SECONDS = 5


@pytest.fixture
async def engine(database_url) -> AsyncIterator[AsyncEngine]:  # noqa: F811
    settings = Settings(_env_file=None, database_url=database_url, db_lock_timeout_ms=200)
    engine = build_engine(settings, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def partner_id(engine) -> AsyncIterator[UUID]:
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    partner_id = uuid4()
    async with sessions() as setup:
        setup.add(
            PartnerRow(
                id=partner_id,
                name="Locked hotel",
                kind="hotel",
                country="Italy",
                city="Rome",
                contact_email="locked@example.com",
                contact_phone="+39 000",
                active=True,
            )
        )
        await setup.commit()
    yield partner_id
    async with sessions() as cleanup:
        await cleanup.execute(delete(PartnerRow).where(PartnerRow.id == partner_id))
        await cleanup.commit()


def locking(partner_id: UUID):
    return select(PartnerRow.id).where(PartnerRow.id == partner_id).with_for_update()


async def test_every_session_has_the_timeouts(database_url):  # noqa: F811
    engine = build_engine(Settings(_env_file=None, database_url=database_url), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            shown = {
                name: await connection.scalar(text(f"SHOW {name}"))
                for name in (
                    "lock_timeout",
                    "statement_timeout",
                    "idle_in_transaction_session_timeout",
                )
            }
    finally:
        await engine.dispose()

    assert shown == {
        "lock_timeout": "5s",
        "statement_timeout": "30s",
        "idle_in_transaction_session_timeout": "1min",
    }


async def test_a_row_lock_held_too_long_ends_in_lock_not_available_then_503(engine, partner_id):
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as holder, sessions() as waiter:
        assert await holder.scalar(locking(partner_id)) == partner_id

        # The holder never lets go: without lock_timeout this would wait forever.
        with pytest.raises(DBAPIError) as raised:
            async with asyncio.timeout(GUARD_SECONDS):
                await waiter.scalar(locking(partner_id))
        await holder.rollback()

    assert raised.value.orig.sqlstate == "55P03"
    response = await handle_database_error(None, raised.value)
    assert response.status_code == 503
    assert response.headers["Retry-After"]


async def test_a_lock_timeout_inside_a_route_answers_503_database_busy(engine, partner_id):
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app()

    @app.get("/test/lock-partner")
    async def lock_partner() -> None:
        async with sessions() as session:
            await session.scalar(locking(partner_id))

    async with sessions() as holder:
        assert await holder.scalar(locking(partner_id)) == partner_id
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with asyncio.timeout(GUARD_SECONDS):
                response = await client.get("/test/lock-partner")
        await holder.rollback()

    assert response.status_code == 503
    assert response.json()["code"] == "database_busy"
    assert response.headers["Retry-After"] == str(DATABASE_BUSY_RETRY_AFTER_SECONDS)


async def test_migrations_give_up_on_a_lock_after_their_lock_timeout(
    engine,
    database_url,  # noqa: F811
    monkeypatch,
):
    """A migration that cannot get its lock fails (the deploy can be retried) instead of
    queueing every app query on that table behind it."""
    monkeypatch.setenv("NOVOYA_DATABASE_URL", database_url)
    monkeypatch.setenv("NOVOYA_DB_MIGRATION_LOCK_TIMEOUT_MS", "1000")
    get_settings.cache_clear()
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    try:
        async with engine.connect() as holder:
            # Alembic reads alembic_version first: it waits for this lock.
            await holder.execute(text("LOCK TABLE alembic_version IN ACCESS EXCLUSIVE MODE"))
            with pytest.raises(DBAPIError) as raised:
                async with asyncio.timeout(GUARD_SECONDS):
                    await asyncio.to_thread(command.current, config)
            await holder.rollback()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()

    assert raised.value.orig.sqlstate == "55P03"
