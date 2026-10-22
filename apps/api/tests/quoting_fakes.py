"""Shared quoting test data and fakes: a priced plan, two people and the ports on memory."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from novoya_api.quoting.application.dto import (
    Person,
    QuotedExtra,
    QuotedItem,
    QuoteDocument,
    QuotedPlan,
)
from novoya_api.quoting.domain.quote import Quote
from novoya_api.shared.domain.value_objects import Locale

PLAN_ID = UUID("00000000-0000-0000-0000-0000000000d1")
WISH_ID = UUID("00000000-0000-0000-0000-0000000000a1")
CLIENT_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_CLIENT = UUID("00000000-0000-0000-0000-000000000002")
AGENT_ID = UUID("00000000-0000-0000-0000-0000000000aa")
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
FRONTEND = "https://novoya.example"

QUOTED = QuotedPlan(
    plan_id=PLAN_ID,
    wish_id=WISH_ID,
    client_id=CLIENT_ID,
    agent_id=AGENT_ID,
    summary="A week by the sea",
    items=(
        QuotedItem(1, "hotel", "Sea view room", "Rooms over the bay", 6, Decimal("900.00")),
        QuotedItem(3, "activity", "Boat trip", "A day at sea", 2, Decimal("289.50")),
    ),
    extras=(
        QuotedExtra("Private guide", "per activity", "on_quote", Decimal("45.00")),
        QuotedExtra("Breakfast", "", "included", None),
    ),
    total=Decimal("1234.50"),
    wish_text="A quiet week in Chania with seafood",
    country="Greece",
    city="Chania",
    persons=2,
    start_date=date(2026, 5, 10),
    end_date=date(2026, 5, 17),
    budget_max=Decimal("1500.00"),
    currency="EUR",
    tags=("style:beach", "food:seafood"),
)
CLIENT_FR = Person(CLIENT_ID, "Alice Martin", "alice@example.com", Locale.FR)
CLIENT_EN = Person(CLIENT_ID, "Alice Martin", "alice@example.com", Locale.EN)
AGENT = Person(AGENT_ID, "Paul Agent", "agent@novoya.example", Locale.EN)


def document(locale: Locale) -> QuoteDocument:
    quote = Quote.issue(PLAN_ID, CLIENT_ID, AGENT_ID, QUOTED.total, locale, NOW)
    client = CLIENT_FR if locale is Locale.FR else CLIENT_EN
    return QuoteDocument(quote, QUOTED, client, AGENT, f"{FRONTEND}/quotes/{quote.id}")


class FakePlanQuoting:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[UUID, UUID]] = []

    async def quote(self, plan_id: UUID, agent_id: UUID) -> QuotedPlan:
        self.calls.append((plan_id, agent_id))
        if self.error is not None:
            raise self.error
        return QUOTED


class FakePeople:
    def __init__(self, *people: Person) -> None:
        self.people = {person.user_id: person for person in people}

    async def get(self, user_id: UUID) -> Person | None:
        return self.people.get(user_id)


class FakeRenderer:
    def __init__(self) -> None:
        self.documents: list[QuoteDocument] = []

    def render(self, document: QuoteDocument) -> bytes:
        self.documents.append(document)
        return b"%PDF-1.7 fake"


class FakeQuotes:
    def __init__(self, *quotes: Quote) -> None:
        self.quotes = {quote.id: quote for quote in quotes}
        self.added: list[Quote] = []

    async def add(self, quote: Quote) -> None:
        self.added.append(quote)
        self.quotes[quote.id] = quote

    async def get(self, quote_id: UUID) -> Quote | None:
        return self.quotes.get(quote_id)


class FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None: ...


class FixedClock:
    def now(self) -> datetime:
        return NOW


def stored_quote() -> Quote:
    quote = Quote.issue(PLAN_ID, CLIENT_ID, AGENT_ID, Decimal("1234.50"), Locale.FR, NOW)
    quote.pdf = b"%PDF-1.7 stored"
    return quote
