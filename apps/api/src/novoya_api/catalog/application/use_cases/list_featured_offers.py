from novoya_api.catalog.application.ports import OfferRepository
from novoya_api.catalog.domain import Offer

# The home page shows this many inspirations.
FEATURED_LIMIT = 3


class ListFeaturedOffers:
    """Offers an agent featured (ADR 0014), listed only: active, not hidden, and so is its
    partner. A hidden or removed offer drops out on the next read."""

    def __init__(self, offers: OfferRepository) -> None:
        self._offers = offers

    async def __call__(self) -> list[Offer]:
        return await self._offers.list_listed_featured(FEATURED_LIMIT)
