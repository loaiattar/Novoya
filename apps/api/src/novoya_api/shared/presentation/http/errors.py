"""One handler that turns domain errors into HTTP responses, for every module.

The status comes from the error's base class; the body is {"code": ..., "detail": ...}.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError

from novoya_api.shared.domain.errors import (
    Conflict,
    DomainError,
    InvalidInput,
    InvalidTransition,
    NotFound,
    PermissionDenied,
    TooLarge,
    TooManyRequests,
    Unauthenticated,
    Unavailable,
)

logger = logging.getLogger(__name__)

STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (Unauthenticated, status.HTTP_401_UNAUTHORIZED),
    (PermissionDenied, status.HTTP_403_FORBIDDEN),
    (NotFound, status.HTTP_404_NOT_FOUND),
    (InvalidTransition, status.HTTP_409_CONFLICT),
    (Conflict, status.HTTP_409_CONFLICT),
    (InvalidInput, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (TooLarge, status.HTTP_413_CONTENT_TOO_LARGE),
    (TooManyRequests, status.HTTP_429_TOO_MANY_REQUESTS),
    (Unavailable, status.HTTP_503_SERVICE_UNAVAILABLE),
]


class ErrorResponse(BaseModel):
    """Body of every error raised by a business rule."""

    code: str
    detail: str


def status_of(error: DomainError) -> int:
    for error_type, status_code in STATUS_BY_ERROR:
        if isinstance(error, error_type):
            return status_code
    return status.HTTP_400_BAD_REQUEST


async def handle_domain_error(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, DomainError)
    body = ErrorResponse(code=error.code, detail=str(error) or error.code)
    headers = {}
    if isinstance(error, TooManyRequests):
        headers["Retry-After"] = str(error.retry_after_seconds)
    return JSONResponse(body.model_dump(), status_code=status_of(error), headers=headers)


async def handle_validation_error(request: Request, error: Exception) -> JSONResponse:
    """Invalid request bodies get the same {code, detail} shape. The input values are left
    out: they can be passwords or personal data."""
    assert isinstance(error, RequestValidationError)
    detail = "; ".join(
        f"{'.'.join(str(part) for part in e['loc'][1:]) or 'body'}: {e['msg']}"
        for e in error.errors()
    )
    body = ErrorResponse(code="invalid_input", detail=detail)
    return JSONResponse(body.model_dump(), status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)


DATABASE_BUSY_RETRY_AFTER_SECONDS = 2

# Listed on every route that uses the database (main.py adds it to those routers), since
# any of them may hit a timeout.
DATABASE_BUSY_RESPONSE = {
    "model": ErrorResponse,
    "description": "database_busy: a lock or statement timeout, or a deadlock. Try again.",
    "headers": {
        "Retry-After": {
            "description": "Seconds to wait before trying again.",
            "schema": {"type": "integer"},
        }
    },
}

# SQLSTATEs of a database that is busy, not of a bug: trying again a moment later works.
# 55P03 lock_not_available (lock_timeout), 57014 query_canceled (statement_timeout),
# 40P01 deadlock_detected (PostgreSQL cancelled one of two transactions waiting on each other).
DATABASE_BUSY_SQLSTATES = frozenset({"55P03", "57014", "40P01"})


async def handle_database_error(request: Request | None, error: Exception) -> JSONResponse:
    """A database timeout or deadlock becomes 503 database_busy with Retry-After. Any other
    database error is raised again, so it stays a 500 with its traceback.

    SQLAlchemy wraps the asyncpg error in a DBAPIError; .orig is its asyncpg adapter error,
    which carries the SQLSTATE. Only its type and SQLSTATE are logged: never the statement or
    its parameters (wish texts, emails)."""
    assert isinstance(error, DBAPIError)
    sqlstate = getattr(error.orig, "sqlstate", None)
    if sqlstate not in DATABASE_BUSY_SQLSTATES:
        raise error
    logger.warning("database busy: %s (SQLSTATE %s)", type(error.orig).__name__, sqlstate)
    body = ErrorResponse(code="database_busy", detail="the database is busy, try again")
    return JSONResponse(
        body.model_dump(),
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={"Retry-After": str(DATABASE_BUSY_RETRY_AFTER_SECONDS)},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(DBAPIError, handle_database_error)
