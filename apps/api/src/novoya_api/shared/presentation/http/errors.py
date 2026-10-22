"""One handler that turns domain errors into HTTP responses, for every module.

The status comes from the error's base class; the body is {"code": ..., "detail": ...}.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
