from collections.abc import Sequence
from datetime import date
from typing import Protocol
from uuid import UUID

from novoya_api.planning.application.dto import ExtraSummary, OfferContact, OfferSummary


class OfferCatalog(Protocol):
    """What planning needs from the partner catalog: offers, and the extras a client adds."""

    async def fitting_offers(
        self,
        country: str,
        city: str | None,
        tags: Sequence[str],
        persons: int,
        start: date,
        end: date,
    ) -> list[OfferSummary]:
        """Listed offers there that fit the group and the whole trip, best first. With tags,
        only offers matching at least one; featured offers come first among equals."""
        ...

    async def summaries_for(self, offer_ids: Sequence[UUID]) -> list[OfferSummary]:
        """Offers by id, even inactive: a saved plan still has to show their titles."""
        ...

    async def contacts_for(self, offer_ids: Sequence[UUID]) -> list[OfferContact]:
        """Offers by id with the partner's name and contact, for the assigned agent."""
        ...

    async def extras_for(self, extra_ids: Sequence[UUID]) -> list[ExtraSummary]:
        """Active extras by id. An inactive or unknown id is left out."""
        ...
