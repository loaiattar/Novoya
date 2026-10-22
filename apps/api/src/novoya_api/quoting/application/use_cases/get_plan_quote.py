from uuid import UUID

from novoya_api.quoting.application.dto import QuoteView
from novoya_api.quoting.application.ports.quote_repository import QuoteRepository
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.shared.domain.errors import PermissionDenied


class GetPlanQuote:
    """The quote of a plan, for the agent who sent it. Not found before it is sent, or for
    an unknown plan; another agent is refused."""

    def __init__(self, quotes: QuoteRepository) -> None:
        self._quotes = quotes

    async def __call__(self, plan_id: UUID, agent_id: UUID) -> QuoteView:
        quote = await self._quotes.get_for_plan(plan_id)
        if quote is None:
            raise QuoteNotFound("no quote for this plan yet")
        if quote.agent_id != agent_id:
            raise PermissionDenied("another agent sent this quote")
        return QuoteView.of(quote)
