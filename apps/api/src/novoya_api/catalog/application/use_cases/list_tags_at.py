from novoya_api.catalog.application.ports import OfferRepository


class ListTagsAt:
    """Tags of listed offers at a destination. If city is None, the whole country."""

    def __init__(self, offers: OfferRepository) -> None:
        self._offers = offers

    async def __call__(self, country: str, city: str | None) -> list[str]:
        tags: set[str] = set()
        for offer, partner in await self._offers.list_at(country, city):
            if offer.is_listed_with(partner):
                tags.update(offer.tags)
        return sorted(tags)
