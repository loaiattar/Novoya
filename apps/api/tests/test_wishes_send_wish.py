"""SendWish is tested with fake ports: a scripted reader, an in-memory catalog and repository."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from novoya_api.shared.domain.errors import TooManyRequests
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from novoya_api.wishes.application.ports.destination_reader import DestinationReading
from novoya_api.wishes.application.use_cases.send_wish import (
    SEND_LIMIT,
    SEND_WINDOW,
    SendWish,
    SendWishCommand,
    SendWishResult,
)
from novoya_api.wishes.domain.errors import InvalidWish
from novoya_api.wishes.domain.panel import Panel, PanelSection, Tag
from novoya_api.wishes.domain.wish import Destination, WishStatus
from tests.accounts.fakes import FrozenClock

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_USER_ID = UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


LISBON = Destination("Portugal", "Lisbon")
PORTO = Destination("Portugal", "Porto")
MARRAKECH = Destination("Morocco", "Marrakech")
ATHENS = Destination("Greece", "Athens")
ROME = Destination("Italy", "Rome")
MADRID = Destination("Spain", "Madrid")
COVERED = [LISBON, PORTO, MARRAKECH, ATHENS, ROME]
LISBON_TAGS = ["style:beach", "style:city", "food:seafood"]


class FakeCatalog:
    def __init__(self, covered, tags) -> None:
        self.covered = covered
        self.tags = tags
        self.tags_asked: list[Destination] = []
        self.calls = 0

    async def covered_destinations(self) -> list[Destination]:
        self.calls += 1
        return list(self.covered)

    async def tags_at(self, destination: Destination) -> list[str]:
        self.calls += 1
        self.tags_asked.append(destination)
        return list(self.tags)


class FakeReader:
    def __init__(self, reading: DestinationReading, events: list[str]) -> None:
        self.reading = reading
        self.events = events
        self.calls: list[tuple[str, list[Destination]]] = []

    async def read(self, text, covered) -> DestinationReading:
        self.calls.append((text, list(covered)))
        self.events.append("read")
        return self.reading


class FakePanelBuilder:
    def __init__(self, events: list[str], panel: Panel | None = None) -> None:
        self.events = events
        self.panel = panel
        self.calls: list[tuple[str, Destination, list[str]]] = []

    async def build(self, text, destination, tags) -> Panel:
        self.calls.append((text, destination, list(tags)))
        self.events.append("build")
        return self.panel if self.panel is not None else Panel.from_tags(tags)


class FakeWishes:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.added = []

    async def add(self, wish) -> None:
        self.events.append("add")
        self.added.append(wish)


class FakeUnitOfWork:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def commit(self) -> None:
        self.events.append("commit")

    async def rollback(self) -> None:
        self.events.append("rollback")


class Setup:
    def __init__(
        self, reading: DestinationReading, covered=COVERED, tags=LISBON_TAGS, panel=None
    ) -> None:
        self.events: list[str] = []
        self.wishes = FakeWishes(self.events)
        self.catalog = FakeCatalog(covered, tags)
        self.reader = FakeReader(reading, self.events)
        self.builder = FakePanelBuilder(self.events, panel)
        self.uow = FakeUnitOfWork(self.events)
        self.limiter_clock = FrozenClock()
        self.limiter = InMemoryRateLimiter(self.limiter_clock)
        self.send_wish = SendWish(
            wishes=self.wishes,
            catalog=self.catalog,
            reader=self.reader,
            panel_builder=self.builder,
            rate_limiter=self.limiter,
            uow=self.uow,
            clock=FixedClock(),
        )


async def send(setup: Setup, text: str = "  A week in Lisbon  ") -> SendWishResult:
    return await setup.send_wish(SendWishCommand(user_id=USER_ID, text=text))


# Every case


async def test_wish_is_created_for_the_user_with_stripped_text_and_clock_time():
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[]))

    result = await send(setup)

    assert result.wish.user_id == USER_ID
    assert result.wish.text == "A week in Lisbon"
    assert result.wish.created_at == NOW
    assert result.wish.updated_at == NOW


async def test_reader_gets_the_stripped_text_and_the_covered_destinations():
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[]))

    await send(setup)

    assert setup.reader.calls == [("A week in Lisbon", COVERED)]


@pytest.mark.parametrize(
    ("reading", "events"),
    [
        (
            DestinationReading(destination=LISBON, suggestions=[]),
            ["rollback", "read", "rollback", "build", "add", "commit"],
        ),
        (
            DestinationReading(destination=MADRID, suggestions=[]),
            ["rollback", "read", "add", "commit"],
        ),
        (
            DestinationReading(destination=None, suggestions=[]),
            ["rollback", "read", "add", "commit"],
        ),
    ],
    ids=["covered", "not_covered", "no_destination"],
)
async def test_wish_is_added_once_then_committed_once(reading, events):
    setup = Setup(reading)

    result = await send(setup)

    assert setup.events == events
    assert setup.wishes.added == [result.wish]


async def test_the_catalog_read_ends_before_the_reader_runs():
    """The reader may wait on a model for seconds: the request must not hold its database
    connection, in an open transaction, during that time."""
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[]))

    await send(setup)

    assert setup.events.index("rollback") < setup.events.index("read")


async def test_tags_are_read_then_the_connection_is_released_before_the_builder_runs():
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[]))

    await send(setup)

    assert setup.events.index("read") < setup.events.index("rollback", 1)
    assert setup.events.index("rollback", 1) < setup.events.index("build")


# Covered destination


async def test_covered_destination_shows_the_panel_of_its_tags():
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[PORTO]))

    result = await send(setup)

    assert result.wish.status is WishStatus.PANEL_SHOWN
    assert result.wish.destination == LISBON
    assert result.wish.panel == Panel.from_tags(LISBON_TAGS)
    assert result.suggestions == []
    assert setup.builder.calls == [("A week in Lisbon", LISBON, LISBON_TAGS)]


async def test_covered_shows_the_builder_panel():
    proposed = Panel(
        sections=(
            PanelSection(
                "style",
                "Travel style",
                True,
                (Tag("beach", "Beach", True), Tag("city", "City")),
            ),
        )
    )
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[]), panel=proposed)

    result = await send(setup)

    assert result.wish.panel == proposed


async def test_covered_drops_tags_the_builder_invented():
    proposed = Panel(
        sections=(
            PanelSection(
                "style",
                "Travel style",
                True,
                (Tag("beach", "Beach", True), Tag("japan", "Japan")),
            ),
            PanelSection("mystery", "Mystery", True, (Tag("ufo", "UFO"),)),
        )
    )
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[]), panel=proposed)

    result = await send(setup)

    assert result.wish.panel == Panel(
        sections=(PanelSection("style", "Travel style", True, (Tag("beach", "Beach", True),)),)
    )


async def test_covered_falls_back_to_catalog_tags_when_the_builder_panel_has_none_left():
    proposed = Panel(sections=(PanelSection("style", "Style", True, (Tag("japan", "Japan"),)),))
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[]), panel=proposed)

    result = await send(setup)

    assert result.wish.panel == Panel.from_tags(LISBON_TAGS)


async def test_covered_destination_uses_the_catalog_spelling():
    setup = Setup(
        DestinationReading(destination=Destination("portugal", " lisbon"), suggestions=[])
    )

    result = await send(setup)

    assert result.wish.destination == LISBON
    assert setup.catalog.tags_asked == [LISBON]


async def test_covered_country_keeps_no_city_in_the_catalog_spelling():
    setup = Setup(DestinationReading(destination=Destination("PORTUGAL"), suggestions=[]))

    result = await send(setup)

    assert result.wish.destination == Destination("Portugal")
    assert setup.catalog.tags_asked == [Destination("Portugal")]


async def test_covered_country_without_city_shows_the_panel():
    portugal = Destination("Portugal")
    setup = Setup(DestinationReading(destination=portugal, suggestions=[]))

    result = await send(setup)

    assert result.wish.status is WishStatus.PANEL_SHOWN
    assert result.wish.destination == portugal
    assert setup.catalog.tags_asked == [portugal]


# Destination not covered


async def test_uncovered_destination_marks_the_wish_not_covered():
    setup = Setup(DestinationReading(destination=MADRID, suggestions=[LISBON]))

    result = await send(setup)

    assert result.wish.status is WishStatus.NOT_COVERED
    assert result.wish.destination == MADRID
    assert result.wish.panel is None
    assert setup.catalog.tags_asked == []
    assert setup.builder.calls == []


async def test_uncovered_destination_suggests_the_covered_reader_suggestions():
    setup = Setup(DestinationReading(destination=MADRID, suggestions=[PORTO, ROME]))

    result = await send(setup)

    assert result.suggestions == [PORTO, ROME]


async def test_suggestions_drop_uncovered_ones_and_use_the_covered_spelling():
    suggestions = [Destination("spain", "barcelona"), Destination(" portugal", "PORTO ")]
    setup = Setup(DestinationReading(destination=MADRID, suggestions=suggestions))

    result = await send(setup)

    assert result.suggestions == [PORTO]


async def test_suggestions_are_deduplicated():
    suggestions = [PORTO, Destination("portugal", "porto"), MARRAKECH]
    setup = Setup(DestinationReading(destination=MADRID, suggestions=suggestions))

    result = await send(setup)

    assert result.suggestions == [PORTO, MARRAKECH]


async def test_suggestions_are_capped_at_three():
    suggestions = [ROME, ATHENS, MARRAKECH, PORTO]
    setup = Setup(DestinationReading(destination=MADRID, suggestions=suggestions))

    result = await send(setup)

    assert result.suggestions == [ROME, ATHENS, MARRAKECH]


async def test_suggestion_without_city_is_replaced_by_the_covered_destination():
    setup = Setup(DestinationReading(destination=MADRID, suggestions=[Destination("Morocco")]))

    result = await send(setup)

    assert result.suggestions == [MARRAKECH]


async def test_no_covered_suggestion_falls_back_to_the_first_three_covered():
    suggestions = [Destination("Spain", "Barcelona")]
    setup = Setup(DestinationReading(destination=MADRID, suggestions=suggestions))

    result = await send(setup)

    assert result.suggestions == [LISBON, PORTO, MARRAKECH]


async def test_no_suggestion_at_all_falls_back_to_the_first_three_covered():
    setup = Setup(DestinationReading(destination=MADRID, suggestions=[]))

    result = await send(setup)

    assert result.suggestions == [LISBON, PORTO, MARRAKECH]


# No destination


async def test_no_destination_keeps_a_draft_and_suggests_every_covered_destination():
    setup = Setup(DestinationReading(destination=None, suggestions=[PORTO]))

    result = await send(setup, "Somewhere warm")

    assert result.wish.status is WishStatus.DRAFT
    assert result.wish.destination is None
    assert result.wish.panel is None
    assert result.suggestions == COVERED
    assert setup.catalog.tags_asked == []
    assert setup.builder.calls == []


# Blank text


@pytest.mark.parametrize("text", ["", "   "])
async def test_blank_text_raises_before_reading_and_saves_nothing(text):
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[]))

    with pytest.raises(InvalidWish):
        await send(setup, text)

    assert setup.reader.calls == []
    assert setup.builder.calls == []
    assert setup.catalog.calls == 0
    assert setup.events == []


async def test_country_wide_coverage_keeps_the_city_of_the_wish():
    # A partner covering all of Morocco: the catalog entry has no city.
    morocco = Destination("Morocco")
    setup = Setup(
        DestinationReading(destination=Destination("morocco", "Fes"), suggestions=[]),
        covered=[morocco],
    )

    result = await send(setup)

    assert result.wish.destination == Destination("Morocco", "Fes")
    assert setup.catalog.tags_asked == [Destination("Morocco", "Fes")]


# Rate limit


async def test_a_client_sends_the_limit_then_gets_too_many_requests_before_any_model_call():
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[]))
    for _ in range(SEND_LIMIT):
        await send(setup)
    setup.events.clear()

    with pytest.raises(TooManyRequests) as error:
        await send(setup)

    assert error.value.code == "too_many_requests"
    assert error.value.retry_after_seconds == SEND_WINDOW.total_seconds()
    assert setup.events == []  # no read, no model, no save
    assert len(setup.wishes.added) == SEND_LIMIT


async def test_the_send_limit_is_per_client():
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[]))
    for _ in range(SEND_LIMIT):
        await send(setup)

    result = await setup.send_wish(SendWishCommand(user_id=OTHER_USER_ID, text="A week in Lisbon"))

    assert result.wish.user_id == OTHER_USER_ID


async def test_the_send_limit_resets_after_the_window():
    setup = Setup(DestinationReading(destination=LISBON, suggestions=[]))
    for _ in range(SEND_LIMIT):
        await send(setup)
    setup.limiter_clock.advance(SEND_WINDOW)

    await send(setup)

    assert len(setup.wishes.added) == SEND_LIMIT + 1
