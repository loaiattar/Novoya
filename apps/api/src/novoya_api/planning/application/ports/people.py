from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from novoya_api.planning.application.dto import Person


class People(Protocol):
    async def search_ids(self, query: str) -> list[UUID]:
        """The ids of the users whose email or name contains `query`."""
        ...

    async def get_many(self, user_ids: Sequence[UUID]) -> dict[UUID, Person]:
        """The clients and agents with these ids. Missing ids are omitted."""
        ...
