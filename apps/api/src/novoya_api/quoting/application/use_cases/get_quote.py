from uuid import UUID

from novoya_api.quoting.application.dto import QuoteDetailView
from novoya_api.quoting.application.ports.people import People
from novoya_api.quoting.application.ports.plans import PlanQuoting
from novoya_api.quoting.application.ports.quote_repository import QuoteRepository
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.shared.application.clock import Clock


class GetQuote:
    """A quote and where it stands, with the trip and the lines the quote page shows, for
    its client or for staff (agents, admins). Anyone else, or a missing id, looks the same:
    not found."""

    def __init__(
        self, quotes: QuoteRepository, plans: PlanQuoting, people: People, clock: Clock
    ) -> None:
        self._quotes = quotes
        self._plans = plans
        self._people = people
        self._clock = clock

    async def __call__(self, quote_id: UUID, reader_id: UUID, staff: bool) -> QuoteDetailView:
        # Without the PDF: the page shows the lines itself and downloads the file apart.
        quote = await self._quotes.get(quote_id, with_pdf=False)
        if quote is None or not quote.readable_by(reader_id, staff):
            raise QuoteNotFound("no such quote")
        plan = await self._plans.priced(quote.plan_id)
        agent = await self._people.get(quote.agent_id)
        return QuoteDetailView.at(quote, quote.status(self._clock.now()), plan, agent)
