from collections.abc import Sequence
from uuid import UUID

from novoya_api.catalog.application.dto import ExtraView
from novoya_api.catalog.application.ports import ExtraRepository


class GetExtras:
    """Listed extras by id, in that order. Inactive, hidden and unknown ids are omitted."""

    def __init__(self, extras: ExtraRepository) -> None:
        self._extras = extras

    async def __call__(self, ids: Sequence[UUID]) -> list[ExtraView]:
        return [ExtraView.of(extra) for extra in await self._extras.list_active_by_ids(ids)]
