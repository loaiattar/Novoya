import re
from dataclasses import dataclass
from uuid import UUID, uuid4

from novoya_api.accounts.domain.errors import InvalidEmail

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class UserId:
    value: UUID

    @classmethod
    def new(cls) -> "UserId":
        return cls(uuid4())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Email:
    """An email address, trimmed and lowercased, so that it can be compared and stored as is."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if len(normalized) > 254 or not _EMAIL_RE.match(normalized):
            raise InvalidEmail("invalid email address")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PlainPassword:
    """A password in clear text. Never logged, never stored."""

    value: str

    def __repr__(self) -> str:
        return "PlainPassword(***)"


@dataclass(frozen=True, slots=True)
class PasswordHash:
    value: str

    def __repr__(self) -> str:
        return "PasswordHash(***)"


@dataclass(frozen=True, slots=True)
class SessionToken:
    """The opaque token given to the browser. Only its hash is stored."""

    value: str

    def __repr__(self) -> str:
        return "SessionToken(***)"
