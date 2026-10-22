from typing import Protocol
from uuid import UUID

from novoya_api.quoting.domain.quote import Quote


class QuoteRepository(Protocol):
    async def add(self, quote: Quote) -> None:
        """Adds the quote with its PDF. One quote per plan: a second one fails."""
        ...

    async def get(self, quote_id: UUID, with_pdf: bool = True) -> Quote | None:
        """The quote, or None. with_pdf=False leaves its pdf empty and skips reading the file."""
        ...
