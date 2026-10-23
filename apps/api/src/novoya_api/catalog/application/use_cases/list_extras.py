from novoya_api.catalog.application.ports import ExtraRepository
from novoya_api.catalog.domain import Extra


class ListExtras:
    """The extras a client can add to a plan: active ones that no agent hid."""

    def __init__(self, extras: ExtraRepository) -> None:
        self._extras = extras

    async def __call__(self) -> list[Extra]:
        return await self._extras.list_active()
