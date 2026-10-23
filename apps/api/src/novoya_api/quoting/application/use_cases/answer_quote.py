from uuid import UUID

from novoya_api.quoting.application.ports.plans import PlanQuoting
from novoya_api.quoting.application.ports.quote_repository import QuoteRepository
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.quoting.domain.quote import QuoteStatus
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork
from novoya_api.shared.domain.errors import PermissionDenied


class AnswerQuote:
    """The client accepts or rejects their quote, with an optional comment. The answer on the
    quote and the plan's new status are committed together.

    Only the quote's client answers. Its agent and admins can read the quote, so they get
    403; anyone else gets 404, as for a read."""

    def __init__(
        self, quotes: QuoteRepository, plans: PlanQuoting, uow: UnitOfWork, clock: Clock
    ) -> None:
        self._quotes = quotes
        self._plans = plans
        self._uow = uow
        self._clock = clock

    async def __call__(
        self,
        quote_id: UUID,
        reader_id: UUID,
        admin: bool,
        answer: QuoteStatus,
        comment: str | None,
    ) -> None:
        quote = await self._quotes.get(quote_id, with_pdf=False)
        if quote is None or not quote.readable_by(reader_id, admin):
            raise QuoteNotFound("no such quote")
        if quote.client_id != reader_id:
            raise PermissionDenied("only the client answers their quote")
        quote.record_answer(answer, comment, self._clock.now())
        await self._quotes.save_answer(quote)
        await self._plans.record_answer(quote.plan_id, accepted=answer is QuoteStatus.ACCEPTED)
        await self._uow.commit()
