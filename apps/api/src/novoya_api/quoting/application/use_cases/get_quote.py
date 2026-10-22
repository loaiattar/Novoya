from uuid import UUID

from novoya_api.quoting.application.dto import QuoteDetailView
from novoya_api.quoting.application.ports.quote_repository import QuoteRepository
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.shared.application.clock import Clock


class GetQuote:
    """A quote and where it stands, for its client or for staff (agents, admins). Anyone
    else, or a missing id, looks the same: not found."""

    def __init__(self, quotes: QuoteRepository, clock: Clock) -> None:
        self._quotes = quotes
        self._clock = clock

    async def __call__(self, quote_id: UUID, reader_id: UUID, staff: bool) -> QuoteDetailView:
        quote = await self._quotes.get(quote_id)
        if quote is None or (not staff and quote.client_id != reader_id):
            raise QuoteNotFound("no such quote")
        return QuoteDetailView.at(quote, self._clock.now())
