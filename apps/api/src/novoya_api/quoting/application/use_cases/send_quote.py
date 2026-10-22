import asyncio
from uuid import UUID

from novoya_api.quoting.application.dto import QuoteDocument, QuoteEmail, QuoteTrip, QuoteView
from novoya_api.quoting.application.ports.notifier import QuoteNotifier
from novoya_api.quoting.application.ports.people import People
from novoya_api.quoting.application.ports.plans import PlanQuoting
from novoya_api.quoting.application.ports.quote_repository import QuoteRepository
from novoya_api.quoting.application.ports.renderer import QuoteRenderer
from novoya_api.quoting.domain.errors import QuoteNotFound
from novoya_api.quoting.domain.quote import Quote
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork
from novoya_api.shared.domain.value_objects import Locale


class SendQuote:
    """The assigned agent sends the quote: the plan becomes quoted, the PDF is rendered and
    saved with the quote, all in one commit. The agent chooses English or French; without a
    choice, the quote is in the client's language. Then the client gets an email, in the
    quote's language, that sends them to the quote in their account."""

    def __init__(
        self,
        plans: PlanQuoting,
        people: People,
        renderer: QuoteRenderer,
        quotes: QuoteRepository,
        notifier: QuoteNotifier,
        uow: UnitOfWork,
        clock: Clock,
        frontend_url: str,
    ) -> None:
        self._plans = plans
        self._people = people
        self._renderer = renderer
        self._quotes = quotes
        self._notifier = notifier
        self._uow = uow
        self._clock = clock
        self._frontend_url = frontend_url.rstrip("/")

    async def __call__(
        self, plan_id: UUID, agent_id: UUID, locale: Locale | None = None
    ) -> QuoteView:
        quoted = await self._plans.quote(plan_id, agent_id)
        client = await self._people.get(quoted.client_id)
        agent = await self._people.get(agent_id)
        if client is None or agent is None:
            # A deleted account between the check and now; the request rolls back.
            raise QuoteNotFound("the client or the agent is gone")
        quote = Quote.issue(
            quoted.plan_id,
            client.user_id,
            agent_id,
            quoted.total,
            locale or client.locale,
            self._clock.now(),
        )
        quote_url = f"{self._frontend_url}/quotes/{quote.id}"
        document = QuoteDocument(quote, quoted, client, agent, quote_url)
        # WeasyPrint takes a few hundred milliseconds of CPU: keep the event loop free.
        quote.pdf = await asyncio.to_thread(self._renderer.render, document)
        await self._quotes.add(quote)
        await self._uow.commit()

        # After the commit: a failed email never undoes the quote, the agent can resend it.
        trip = QuoteTrip(quoted.country, quoted.city, quoted.start_date, quoted.end_date)
        email = QuoteEmail(client.email, client.name, quote.locale, trip, quote_url)
        return QuoteView.of(quote, await self._notifier.send_quote_ready(email))
