from novoya_api.catalog.application.ports import ExtraRepository
from novoya_api.catalog.domain import Extra


class ListAllExtras:
    """Every extra, inactive and hidden ones too, so an agent can show one again."""

    def __init__(self, extras: ExtraRepository) -> None:
        self._extras = extras

    async def __call__(self) -> list[Extra]:
        return await self._extras.list_all()
