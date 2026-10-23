from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from novoya_api.wishes.domain.wish import Destination


@dataclass(frozen=True)
class DestinationReading:
    destination: Destination | None  # None: the text names no place
    suggestions: list[Destination]  # covered places close to an uncovered one


class DestinationReader(Protocol):
    """Finds where the client wants to go in the wish text."""

    async def read(self, text: str, covered: Sequence[Destination]) -> DestinationReading: ...
