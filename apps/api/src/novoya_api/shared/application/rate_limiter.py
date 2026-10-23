from datetime import timedelta
from typing import Protocol


class RateLimiter(Protocol):
    async def hit(self, key: str, limit: int, window: timedelta) -> None:
        """Count one attempt for `key`. Raise TooManyRequests past `limit` in `window`."""
        ...

    async def reset(self, key: str) -> None: ...
