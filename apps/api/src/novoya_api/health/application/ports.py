from typing import Protocol


class DatabaseProbe(Protocol):
    """Checks that the database answers."""

    async def ping(self) -> None:
        """Return if the database answers, raise otherwise."""
        ...
