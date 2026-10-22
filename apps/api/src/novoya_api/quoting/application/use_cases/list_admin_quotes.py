from datetime import datetime
from uuid import UUID

from novoya_api.quoting.application.dto import AdminQuoteView, Person, QuoteTrip
from novoya_api.quoting.application.ports.people import People
from novoya_api.quoting.application.ports.plans import PlanQuoting
from novoya_api.quoting.application.ports.quote_repository import (
    ADMIN_CAP,
    ADMIN_PAGE,
    QuoteRepository,
)
from novoya_api.quoting.domain.quote import Quote, QuoteStatus
from novoya_api.shared.application.clock import Clock

NO_TRIP = QuoteTrip(None, None, None, None)


class ListAdminQuotes:
    """Every client's quotes, newest first, for the admin overview: number, client, trip,
    total, validity and status. The search matches the client's email or name, or the
    destination. plan_id keeps the quote of one plan, for the plan's page."""

    def __init__(
        self, quotes: QuoteRepository, plans: PlanQuoting, people: People, clock: Clock
    ) -> None:
        self._quotes = quotes
        self._plans = plans
        self._people = people
        self._clock = clock

    async def __call__(
        self,
        status: QuoteStatus | None = None,
        query: str | None = None,
        plan_id: UUID | None = None,
        *,
        limit: int = ADMIN_PAGE,
        offset: int = 0,
    ) -> list[AdminQuoteView]:
        now = self._clock.now()
        query = query.strip() if query else None
        # The status is a column of the quote; only the text search goes through the plans.
        plan_ids: list[UUID] | None = None
        if query:
            plan_ids = await self._plans.find_ids(query, await self._people.search_ids(query))
        if plan_id is not None:
            plan_ids = [plan_id] if plan_ids is None or plan_id in plan_ids else []
        if plan_ids == []:
            return []
        quotes = await self._quotes.search(
            plan_ids,
            status,
            now,
            limit=min(max(limit, 1), ADMIN_CAP),
            offset=max(offset, 0),
        )
        trips = await self._plans.trips([quote.plan_id for quote in quotes])
        people = await self._people.get_many([quote.client_id for quote in quotes])
        return [
            _view(quote, trips.get(quote.plan_id, NO_TRIP), people.get(quote.client_id), now)
            for quote in quotes
        ]


def _view(quote: Quote, trip: QuoteTrip, client: Person | None, now: datetime) -> AdminQuoteView:
    return AdminQuoteView(
        id=quote.id,
        number=quote.number,
        plan_id=quote.plan_id,
        status=quote.status(now).value,
        total=quote.total,
        currency=quote.currency,
        locale=quote.locale.value,
        sent_at=quote.sent_at,
        valid_until=quote.valid_until,
        trip=trip,
        client=client,
    )
