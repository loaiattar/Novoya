import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

# Without a Retry-After, or with one we can't read. Over MAX_SECONDS is taken as a mistake:
# the model is tried again within the hour, and a new 429 pauses it again.
DEFAULT_SECONDS = 300
MAX_SECONDS = 3600


class ModelPause:
    """While OpenRouter answers 429 (the shared key is out of quota), model calls pause, so
    every step goes straight to its fallback instead of waiting for each model to fail.

    In memory, for the whole process, like the rate limiter: fine with one API instance.
    `clock` gives monotonic seconds; tests pass their own."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._until = 0.0

    def start(self, seconds: float) -> None:
        self._until = max(self._until, self._clock() + seconds)

    def remaining(self) -> float:
        """Seconds left in the pause; 0 when the model may be called."""
        return max(0.0, self._until - self._clock())

    def active(self) -> bool:
        return self.remaining() > 0


def pause_seconds(retry_after: str | None) -> float:
    """How long to pause for a Retry-After header: seconds or an HTTP date. A missing, past
    or unreadable value gives DEFAULT_SECONDS; a longer one is capped at MAX_SECONDS."""
    if retry_after is None:
        return DEFAULT_SECONDS
    value = retry_after.strip()
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError):
            return DEFAULT_SECONDS
    if seconds <= 0:
        return DEFAULT_SECONDS
    return min(seconds, MAX_SECONDS)
