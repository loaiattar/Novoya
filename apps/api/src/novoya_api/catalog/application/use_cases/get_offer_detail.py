from uuid import UUID

from novoya_api.catalog.application.ports import OfferRepository
from novoya_api.catalog.domain import Offer, OfferNotFound


class GetOfferDetail:
    """A listed offer for its page: indicative price, months and terms. Unlisted is not found."""

    def __init__(self, offers: OfferRepository) -> None:
        self._offers = offers

    async def __call__(self, offer_id: UUID) -> Offer:
        for offer, partner in await self._offers.list_by_ids([offer_id]):
            if offer.is_listed_with(partner):
                return offer
        raise OfferNotFound("no such offer")
