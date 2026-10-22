from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from novoya_api.catalog.domain import Extra, Offer, Partner, Review


class PartnerRepository(Protocol):
    async def list_all(self) -> list[Partner]:
        """Every partner, active or not. The use case decides who is listed."""
        ...

    async def get(self, partner_id: UUID) -> Partner | None: ...

    async def add(self, partner: Partner) -> None: ...

    async def save(self, partner: Partner) -> None: ...


class OfferRepository(Protocol):
    async def list_with_partners(self) -> list[tuple[Offer, Partner]]:
        """Every offer with its partner. The use case decides which are listed."""
        ...

    async def list_listed_destinations(self) -> list[tuple[str, str]]:
        """Distinct country, city of listed offers, sorted.

        Listed means an active, not hidden offer of an active, not hidden partner.
        """
        ...

    async def list_at(self, country: str, city: str | None) -> list[tuple[Offer, Partner]]:
        """Offers at this destination, with their partner. city None means the whole country."""
        ...

    async def get(self, offer_id: UUID) -> Offer | None: ...

    async def list_by_ids(self, ids: Sequence[UUID]) -> list[tuple[Offer, Partner]]:
        """Offers with their partner, including inactive. Missing ids are omitted."""
        ...

    async def add(self, offer: Offer) -> None: ...

    async def save(self, offer: Offer) -> None: ...


class ReviewRepository(Protocol):
    async def list_at(self, country: str | None, city: str | None, limit: int) -> list[Review]:
        """Published reviews, newest first, at most `limit`. Hidden ones are omitted.
        None for country or city means any."""
        ...

    async def list_all(self) -> list[Review]:
        """Every review still in the database, hidden ones too, newest first."""
        ...

    async def get(self, review_id: UUID) -> Review | None: ...

    async def save(self, review: Review) -> None: ...


class ExtraRepository(Protocol):
    async def list_all(self) -> list[Extra]:
        """Every extra, inactive and hidden ones too, for agents."""
        ...

    async def list_active(self) -> list[Extra]:
        """Listed extras: active and not hidden."""
        ...

    async def list_active_by_ids(self, ids: Sequence[UUID]) -> list[Extra]:
        """Listed extras by id, in that order. Inactive, hidden and unknown ids are omitted."""
        ...

    async def get(self, extra_id: UUID) -> Extra | None: ...

    async def save(self, extra: Extra) -> None: ...
