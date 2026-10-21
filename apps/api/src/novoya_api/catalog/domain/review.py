from dataclasses import dataclass
from datetime import date
from uuid import UUID

from novoya_api.shared.domain.errors import InvalidInput


class InvalidReview(InvalidInput):
    """The rating is not 1 to 5, or the text or the author is empty."""

    code = "invalid_review"


@dataclass(frozen=True)
class Review:
    """A traveller's published review of a trip to a destination.

    Only reviews the traveller agreed to publish reach Novoya, already pseudonymised: the
    author is "First name I." or "Voyageur anonyme", kept as DÉTOUR wrote it (ADR 0014)."""

    id: UUID
    country: str
    city: str
    rating: int
    reviewed_on: date
    text: str
    author: str

    def __post_init__(self) -> None:
        if not 1 <= self.rating <= 5:
            raise InvalidReview("the rating goes from 1 to 5")
        if not self.text.strip():
            raise InvalidReview("the text is empty")
        if not self.author.strip():
            raise InvalidReview("the author is empty")
