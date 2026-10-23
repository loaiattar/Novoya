from uuid import UUID

from novoya_api.quoting.application.dto import PlanQuoteView, QuoteView
from novoya_api.quoting.application.ports.quote_repository import QuoteRepository
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.domain.errors import PermissionDenied


class GetPlanQuote:
    """The quote of a plan and where it stands, with the client's answer and comment, for
    the agent who sent it or an admin, as on GET /quotes/{id}. Not found before it is sent,
    or for an unknown plan; another agent is refused."""

    def __init__(self, quotes: QuoteRepository, clock: Clock) -> None:
        self._quotes = quotes
        self._clock = clock

    async def __call__(self, plan_id: UUID, reader_id: UUID, admin: bool) -> PlanQuoteView:
        quote = await self._quotes.get_for_plan(plan_id)
        if quote is None:
            raise QuoteNotFound("no quote for this plan yet")
        if not admin and quote.agent_id != reader_id:
            raise PermissionDenied("another agent sent this quote")
        return PlanQuoteView(
            quote=QuoteView.of(quote),
            status=quote.status(self._clock.now()),
            decided_at=quote.decided_at,
            client_comment=quote.client_comment,
        )
