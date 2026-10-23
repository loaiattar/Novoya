from uuid import UUID

from novoya_api.catalog.application.ports import OfferRepository
from novoya_api.catalog.domain import Offer


class ListOffers:
    """Every offer, including inactive ones, so an agent can reactivate them. Only one
    partner's offers when partner_id is given (an unknown partner has none)."""

    def __init__(self, offers: OfferRepository) -> None:
        self._offers = offers

    async def __call__(self, partner_id: UUID | None = None) -> list[Offer]:
        return [
            offer
            for offer, _partner in await self._offers.list_with_partners()
            if partner_id is None or offer.partner_id == partner_id
        ]
