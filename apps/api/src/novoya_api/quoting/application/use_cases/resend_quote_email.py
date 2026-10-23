from datetime import timedelta
from uuid import UUID

from novoya_api.quoting.application.dto import QuoteEmail, QuoteTrip
from novoya_api.quoting.application.ports.notifier import QuoteNotifier
from novoya_api.quoting.application.ports.people import People
from novoya_api.quoting.application.ports.plans import PlanQuoting
from novoya_api.quoting.application.ports.quote_repository import QuoteRepository
from novoya_api.quoting.domain.errors import QuoteEmailNotSent, QuoteNotFound
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.domain.errors import PermissionDenied

# Per quote, whoever resends: the client's inbox gets at most this many in an hour.
RESENDS_PER_HOUR = 3


class ResendQuoteEmail:
    """Sends the "your quote is ready" email again, when the first one did not go out. Only
    the agent who sent the quote, or an admin, may do it, and only RESENDS_PER_HOUR times an
    hour for one quote (429 after that), so a loop cannot flood the client's inbox."""

    def __init__(
        self,
        quotes: QuoteRepository,
        plans: PlanQuoting,
        people: People,
        notifier: QuoteNotifier,
        rate_limiter: RateLimiter,
        frontend_url: str,
    ) -> None:
        self._quotes = quotes
        self._plans = plans
        self._people = people
        self._notifier = notifier
        self._rate_limiter = rate_limiter
        self._frontend_url = frontend_url.rstrip("/")

    async def __call__(self, quote_id: UUID, caller_id: UUID, admin: bool) -> None:
        quote = await self._quotes.get(quote_id)
        if quote is None:
            raise QuoteNotFound("no such quote")
        if not admin and quote.agent_id != caller_id:
            raise PermissionDenied("only the agent who sent the quote, or an admin")
        # After the checks: someone who may not resend cannot use up the quote's attempts.
        # A refused email counts too: it still reached the email server.
        await self._rate_limiter.hit(
            f"quote_email:{quote.id}", RESENDS_PER_HOUR, timedelta(hours=1)
        )
        client = await self._people.get(quote.client_id)
        if client is None:
            raise QuoteNotFound("the client is gone")
        # The wish as it is now, not as quoted: if its dates changed since, this email can
        # differ from the PDF. Rare, and keeping a copy on the quote would need a migration.
        trip = await self._plans.trip(quote.plan_id) or QuoteTrip(None, None, None, None)
        email = QuoteEmail(
            client.email,
            client.name,
            quote.locale,
            trip,
            f"{self._frontend_url}/quotes/{quote.id}",
        )
        if not await self._notifier.send_quote_ready(email):
            raise QuoteEmailNotSent("the email server did not take the email, try again later")
