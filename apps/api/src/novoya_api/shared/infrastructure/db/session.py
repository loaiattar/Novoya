from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from novoya_api.config import Settings, get_settings


def server_settings(settings: Settings) -> dict[str, str]:
    """PostgreSQL settings sent by asyncpg when it opens a connection, in milliseconds."""
    return {
        "lock_timeout": str(settings.db_lock_timeout_ms),
        "statement_timeout": str(settings.db_statement_timeout_ms),
        "idle_in_transaction_session_timeout": str(settings.db_idle_in_transaction_timeout_ms),
    }


def build_engine(settings: Settings, **options: Any) -> AsyncEngine:
    # hide_parameters: database errors never print the values (wish texts, emails) in logs.
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"server_settings": server_settings(settings)},
        **options,
    )


@lru_cache
def get_engine() -> AsyncEngine:
    return build_engine(get_settings())


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """One session per request."""
    async with get_sessionmaker()() as session:
        yield session


async def close_db() -> None:
    """Close the pool so a CLI command can leave without 'Event loop is closed'."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
