"""Database timeouts: the settings, the engine that sets them, and the 503 a timeout becomes.

No database here; tests/test_db_timeouts_sql.py checks them against PostgreSQL.
"""

import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError

from novoya_api.config import Settings
from novoya_api.main import create_app
from novoya_api.shared.infrastructure.db import session as db_session
from novoya_api.shared.presentation.http import errors
from novoya_api.shared.presentation.http.errors import (
    DATABASE_BUSY_RETRY_AFTER_SECONDS,
    register_error_handlers,
)


def test_timeouts_have_safe_defaults(monkeypatch):
    for name in ("LOCK", "STATEMENT", "IDLE_IN_TRANSACTION", "MIGRATION_LOCK"):
        monkeypatch.delenv(f"NOVOYA_DB_{name}_TIMEOUT_MS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.db_lock_timeout_ms == 5_000
    assert settings.db_statement_timeout_ms == 30_000
    assert settings.db_idle_in_transaction_timeout_ms == 60_000
    assert settings.db_migration_lock_timeout_ms == 10_000


def test_timeouts_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("NOVOYA_DB_STATEMENT_TIMEOUT_MS", "600000")

    assert Settings(_env_file=None).db_statement_timeout_ms == 600_000


@pytest.mark.parametrize(
    ("field", "value"),
    [
        # 0 turns a PostgreSQL timeout off: never allowed, a raise has a ceiling instead.
        ("db_lock_timeout_ms", 0),
        ("db_lock_timeout_ms", 99),
        ("db_lock_timeout_ms", 60_001),
        ("db_statement_timeout_ms", 0),
        ("db_statement_timeout_ms", 999),
        ("db_statement_timeout_ms", 600_001),
        ("db_idle_in_transaction_timeout_ms", 0),
        ("db_idle_in_transaction_timeout_ms", 999),
        ("db_idle_in_transaction_timeout_ms", 3_600_001),
        ("db_migration_lock_timeout_ms", 0),
        ("db_migration_lock_timeout_ms", 999),
        ("db_migration_lock_timeout_ms", 600_001),
    ],
)
def test_timeouts_outside_their_bounds_are_refused(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_server_settings_are_the_timeouts_in_milliseconds():
    settings = Settings(
        _env_file=None,
        db_lock_timeout_ms=1_000,
        db_statement_timeout_ms=2_000,
        db_idle_in_transaction_timeout_ms=3_000,
    )

    assert db_session.server_settings(settings) == {
        "lock_timeout": "1000",
        "statement_timeout": "2000",
        "idle_in_transaction_session_timeout": "3000",
    }


def test_the_engine_sets_the_timeouts_on_every_connection(monkeypatch):
    calls = []
    monkeypatch.setattr(
        db_session, "create_async_engine", lambda url, **options: calls.append(options)
    )
    monkeypatch.setattr(db_session, "get_settings", lambda: Settings(_env_file=None))
    db_session.get_engine.cache_clear()
    try:
        db_session.get_engine()
    finally:
        db_session.get_engine.cache_clear()

    assert calls[0]["connect_args"] == {
        "server_settings": {
            "lock_timeout": "5000",
            "statement_timeout": "30000",
            "idle_in_transaction_session_timeout": "60000",
        }
    }
    assert calls[0]["hide_parameters"] is True


class FakeAsyncpgError(Exception):
    """Like SQLAlchemy's asyncpg adapter error: the SQLSTATE is on .sqlstate."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__("canceling statement")
        self.sqlstate = sqlstate


def failing_app(sqlstate: str) -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        statement = "SELECT * FROM wishes WHERE text = $1"
        raise DBAPIError(statement, ("secret-wish-text",), FakeAsyncpgError(sqlstate))

    return app


async def call(app: FastAPI):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/boom")


@pytest.mark.parametrize(
    "sqlstate",
    [
        "55P03",  # lock_not_available: lock_timeout
        "57014",  # query_canceled: statement_timeout
        "40P01",  # deadlock_detected
    ],
)
async def test_a_database_timeout_returns_503_database_busy(sqlstate):
    response = await call(failing_app(sqlstate))

    assert response.status_code == 503
    assert response.json()["code"] == "database_busy"
    assert response.headers["Retry-After"] == str(DATABASE_BUSY_RETRY_AFTER_SECONDS)
    assert "secret-wish-text" not in response.text


async def test_another_database_error_stays_a_500():
    response = await call(failing_app("23505"))  # unique_violation: a bug, not a busy database

    assert response.status_code == 500


async def test_a_database_timeout_logs_its_type_and_sqlstate_only(caplog, monkeypatch):
    # Alembic's fileConfig (migration tests) disables the loggers that already exist.
    monkeypatch.setattr(errors.logger, "disabled", False)
    with caplog.at_level(logging.WARNING, logger=errors.logger.name):
        await call(failing_app("55P03"))

    assert "55P03" in caplog.text
    assert "FakeAsyncpgError" in caplog.text
    assert "secret-wish-text" not in caplog.text
    assert "SELECT" not in caplog.text


# Routes that never return database_busy: /health never touches the database, and
# /health/db answers its own 503 (the Health body) when the database does not answer.
NO_DATABASE_BUSY = {"/health", "/health/db"}


def test_the_openapi_schema_lists_503_database_busy_on_every_database_route():
    paths = create_app().openapi()["paths"]

    for path, methods in paths.items():
        if path in NO_DATABASE_BUSY:
            continue
        for method, operation in methods.items():
            busy = operation["responses"].get("503")
            where = f"{method.upper()} {path}"
            assert busy is not None, f"{where} has no 503"
            assert "database_busy" in busy["description"], f"{where}: {busy['description']}"
            assert "Retry-After" in busy.get("headers", {}), f"{where} has no Retry-After"
            assert busy["content"]["application/json"]["schema"] == {
                "$ref": "#/components/schemas/ErrorResponse"
            }, where


def test_the_quote_email_resend_documents_both_of_its_503s():
    resend = create_app().openapi()["paths"]["/agent/quotes/{quote_id}/email"]["post"]

    description = resend["responses"]["503"]["description"]
    assert "email_not_sent" in description
    assert "database_busy" in description


def test_the_health_routes_do_not_list_database_busy():
    paths = create_app().openapi()["paths"]

    assert "503" not in paths["/health"]["get"]["responses"]
    db_health = paths["/health/db"]["get"]["responses"]["503"]
    assert db_health["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Health"
    }
    assert "database_busy" not in db_health["description"]
