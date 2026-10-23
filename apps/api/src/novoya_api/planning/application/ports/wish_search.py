from collections.abc import Sequence
from typing import Protocol
from uuid import UUID


class WishSearch(Protocol):
    async def matching(self, query: str, user_ids: Sequence[UUID]) -> list[UUID]:
        """The ids of the wishes whose destination contains `query`, or that one of `user_ids`
        sent."""
        ...
