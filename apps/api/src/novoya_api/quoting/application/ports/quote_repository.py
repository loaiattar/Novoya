from typing import Protocol
from uuid import UUID

from novoya_api.quoting.domain.quote import Quote


class QuoteRepository(Protocol):
    async def add(self, quote: Quote) -> None:
        """Adds the quote with its PDF. One quote per plan: a second one fails."""
        ...

    async def get(self, quote_id: UUID) -> Quote | None: ...

    async def get_for_plan(self, plan_id: UUID) -> Quote | None:
        """The plan's quote, or None before it is sent. A plan has at most one."""
        ...
