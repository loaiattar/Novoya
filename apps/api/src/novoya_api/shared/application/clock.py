from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Tells the time, so that tests can freeze it."""

    def now(self) -> datetime:
        """The current time, in UTC, timezone aware."""
        ...
