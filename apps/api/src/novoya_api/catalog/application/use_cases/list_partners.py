from novoya_api.catalog.application.ports import PartnerRepository
from novoya_api.catalog.domain import Partner


class ListPartners:
    """Every partner, including inactive ones, so an agent can reactivate them."""

    def __init__(self, partners: PartnerRepository) -> None:
        self._partners = partners

    async def __call__(self) -> list[Partner]:
        return await self._partners.list_all()
