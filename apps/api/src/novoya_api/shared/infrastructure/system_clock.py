from datetime import UTC, datetime


class SystemClock:
    """Clock implemented with the system time."""

    def now(self) -> datetime:
        return datetime.now(UTC)
