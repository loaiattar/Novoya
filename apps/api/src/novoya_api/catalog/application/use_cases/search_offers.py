from datetime import date

from novoya_api.catalog.application.dto import OfferView
from novoya_api.catalog.application.ports import OfferRepository


class SearchOffers:
    """Listed offers at a destination that fit the group size and the whole trip.

    With tags, an offer needs at least one of them; offers matching more tags come first.
    Without tags, every fitting offer comes back. Featured offers come first among equals.
    No budget filter: the price of a trip is negotiated, an offer's price is only indicative."""

    def __init__(self, offers: OfferRepository) -> None:
        self._offers = offers

    async def __call__(
        self,
        country: str,
        city: str | None,
        tags: list[str],
        persons: int,
        start: date,
        end: date,
    ) -> list[OfferView]:
        wanted = {tag.lower() for tag in tags}
        ranked: list[tuple[int, OfferView]] = []
        for offer, partner in await self._offers.list_at(country, city):
            if not offer.is_listed_with(partner) or not offer.fits(persons, start, end):
                continue
            matches = len(wanted & {tag.lower() for tag in offer.tags})
            if wanted and not matches:
                continue
            ranked.append((matches, OfferView.of(offer, partner)))
        ranked.sort(key=lambda item: (-item[0], not item[1].featured, item[1].title))
        return [view for _matches, view in ranked]
