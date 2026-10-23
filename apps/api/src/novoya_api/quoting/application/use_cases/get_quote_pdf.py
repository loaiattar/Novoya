from uuid import UUID

from novoya_api.quoting.application.dto import QuotePdf
from novoya_api.quoting.application.ports.quote_repository import QuoteRepository
from novoya_api.quoting.domain.errors import QuoteNotFound


class GetQuotePdf:
    """The quote's PDF, for its client, the agent who sent it or an admin. Anyone else
    (another agent too), or a missing id, looks the same: not found."""

    def __init__(self, quotes: QuoteRepository) -> None:
        self._quotes = quotes

    async def __call__(self, quote_id: UUID, reader_id: UUID, admin: bool) -> QuotePdf:
        quote = await self._quotes.get(quote_id)
        if quote is None or not quote.readable_by(reader_id, admin):
            raise QuoteNotFound("no such quote")
        if quote.pdf is None:
            raise RuntimeError(f"quote {quote.id} was read without its PDF")
        return QuotePdf(f"{quote.number}.pdf", quote.pdf)
