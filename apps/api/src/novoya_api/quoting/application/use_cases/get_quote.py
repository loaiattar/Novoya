from uuid import UUID

from novoya_api.quoting.application.dto import QuoteDetailView
from novoya_api.quoting.application.ports.plans import PlanQuoting
from novoya_api.quoting.application.ports.quote_repository import QuoteRepository
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.shared.application.clock import Clock


class GetQuote:
    """A quote and where it stands, for its client or for staff (agents, admins). Anyone
    else, or a missing id, looks the same: not found."""

    def __init__(self, quotes: QuoteRepository, plans: PlanQuoting, clock: Clock) -> None:
        self._quotes = quotes
        self._plans = plans
        self._clock = clock

    async def __call__(self, quote_id: UUID, reader_id: UUID, staff: bool) -> QuoteDetailView:
        # Without the PDF: this read only needs the numbers, and the page may call it often.
        quote = await self._quotes.get(quote_id, with_pdf=False)
        if quote is None or not quote.readable_by(reader_id, staff):
            raise QuoteNotFound("no such quote")
        answer = await self._plans.answer(quote.plan_id)
        return QuoteDetailView.at(quote, quote.status(self._clock.now(), answer))
