"""Errors raised when a business rule is broken.

The presentation layer turns them into HTTP status codes; the domain never knows about HTTP.
Each error has a stable `code` that the API returns, so the frontend can translate it.
"""


class DomainError(Exception):
    """Base class for every business rule violation."""

    code = "domain_error"


class NotFound(DomainError):
    """The requested object does not exist, or the caller may not see it."""

    code = "not_found"


class PermissionDenied(DomainError):
    """The caller is known but may not do this, for example a client calling an agent action."""

    code = "forbidden"


class InvalidTransition(DomainError):
    """A status change that the rules do not allow, for example quoting a plan twice."""

    code = "invalid_transition"


class Unauthenticated(DomainError):
    """The caller is not signed in, or their session is no longer valid."""

    code = "unauthenticated"


class Conflict(DomainError):
    """The action clashes with the current state, for example an email that is already used."""

    code = "conflict"


class InvalidInput(DomainError):
    """The input is well formed but breaks a business rule, for example a weak password."""

    code = "invalid_input"


class Unavailable(DomainError):
    """A service the action needs, for example the email server, did not answer. Try again."""

    code = "unavailable"


class TooManyRequests(DomainError):
    """The caller tried too often. They may try again after `retry_after_seconds`."""

    code = "too_many_requests"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"try again in {retry_after_seconds} seconds")
        self.retry_after_seconds = retry_after_seconds
