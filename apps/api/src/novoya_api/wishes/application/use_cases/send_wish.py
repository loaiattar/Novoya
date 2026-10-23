from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.application.unit_of_work import UnitOfWork
from novoya_api.wishes.application.ports.catalog import Catalog
from novoya_api.wishes.application.ports.destination_reader import DestinationReader
from novoya_api.wishes.application.ports.panel_builder import PanelBuilder
from novoya_api.wishes.application.ports.wish_repository import WishRepository
from novoya_api.wishes.domain.panel import Panel
from novoya_api.wishes.domain.wish import Destination, Wish, find_covered

MAX_SUGGESTIONS = 3
# Each wish may call the model twice; free models share their quota between all clients.
SEND_LIMIT = 20
SEND_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class SendWishCommand:
    user_id: UUID
    text: str


@dataclass(frozen=True)
class SendWishResult:
    wish: Wish
    suggestions: list[Destination]


class SendWish:
    """Save the client's wish and check whether our partners cover the destination.

    Covered: the wish shows the panel. Not covered: covered destinations are suggested, and
    the wish is kept so the team sees the demand. No destination in the text: the wish stays
    a draft and every covered destination is suggested.

    The reader and the builder may use an LLM. Coverage is decided here, from the catalog,
    and every tag on the panel must come from the offers at that destination. Each client
    sends at most SEND_LIMIT wishes per SEND_WINDOW, counted before any model call."""

    def __init__(
        self,
        wishes: WishRepository,
        catalog: Catalog,
        reader: DestinationReader,
        panel_builder: PanelBuilder,
        rate_limiter: RateLimiter,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._wishes = wishes
        self._catalog = catalog
        self._reader = reader
        self._panel_builder = panel_builder
        self._rate_limiter = rate_limiter
        self._uow = uow
        self._clock = clock

    async def __call__(self, cmd: SendWishCommand) -> SendWishResult:
        await self._rate_limiter.hit(f"wishes:send:{cmd.user_id}", SEND_LIMIT, SEND_WINDOW)
        wish = Wish.create(cmd.user_id, cmd.text, self._clock.now())
        covered = await self._catalog.covered_destinations()
        # Nothing to save yet: end the read so the connection is not held while the model reads.
        await self._uow.rollback()
        reading = await self._reader.read(wish.text, covered)

        suggestions: list[Destination] = []
        if reading.destination is None:
            suggestions = list(covered)
        elif match := find_covered(reading.destination, covered):
            # The catalog's spelling, so later steps find the offers; keep the wish's precision.
            # A country-wide entry has no city: then the wish's own city is kept.
            city = (match.city or reading.destination.city) if reading.destination.city else None
            destination = Destination(match.country, city)
            tags = await self._catalog.tags_at(destination)
            # The builder may wait on a model: do not hold the connection during that call.
            await self._uow.rollback()
            proposed = await self._panel_builder.build(wish.text, destination, tags)
            panel = proposed.restricted_to(tags)
            if not panel.sections:
                panel = Panel.from_tags(tags)
            wish.show_panel(destination, panel, self._clock.now())
        else:
            wish.mark_not_covered(reading.destination, self._clock.now())
            suggestions = _covered_suggestions(reading.suggestions, covered)

        await self._wishes.add(wish)
        await self._uow.commit()
        return SendWishResult(wish, suggestions)


def _covered_suggestions(
    proposed: list[Destination], covered: list[Destination]
) -> list[Destination]:
    """Keep only what we really cover, in the catalog's spelling; the model may invent."""
    kept: list[Destination] = []
    for destination in proposed:
        match = find_covered(destination, covered)
        if match and match not in kept:
            kept.append(match)
    return kept[:MAX_SUGGESTIONS] or covered[:MAX_SUGGESTIONS]
