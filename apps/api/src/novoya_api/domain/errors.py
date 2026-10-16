"""Errors raised when a business rule is broken.

The presentation layer turns them into HTTP status codes; the domain never knows about HTTP.
"""


class DomainError(Exception):
    """Base class for every business rule violation."""


class NotFound(DomainError):
    """The requested object does not exist, or the caller may not see it."""


class InvalidTransition(DomainError):
    """A status change that the rules do not allow, for example quoting a plan twice."""
