"""Value objects used by several modules."""

from enum import StrEnum


class Locale(StrEnum):
    """The user's language: emails, the quote PDF and the interface use it."""

    EN = "en"
    FR = "fr"

    @classmethod
    def from_hint(cls, hint: str | None) -> "Locale":
        """fr if the hint (an Accept-Language header, a language code) starts with fr, else en."""
        return cls.FR if hint and hint.strip().lower().startswith("fr") else cls.EN
