from novoya_api.catalog.application.ports import OfferRepository


class ListDestinations:
    """Destinations with at least one listed offer: active, not hidden, and so is its partner."""

    def __init__(self, offers: OfferRepository) -> None:
        self._offers = offers

    async def __call__(self) -> list[tuple[str, str]]:
        return await self._offers.list_listed_destinations()
