from collections.abc import Sequence
from uuid import UUID

from novoya_api.catalog.application.dto import OfferView
from novoya_api.catalog.application.ports import OfferRepository


class GetOffers:
    """Offers by id, in that order. Inactive rows stay: a saved plan still needs their titles."""

    def __init__(self, offers: OfferRepository) -> None:
        self._offers = offers

    async def __call__(self, ids: Sequence[UUID]) -> list[OfferView]:
        pairs = await self._offers.list_by_ids(ids)
        by_id = {offer.id: OfferView.of(offer, partner) for offer, partner in pairs}
        return [by_id[offer_id] for offer_id in ids if offer_id in by_id]
