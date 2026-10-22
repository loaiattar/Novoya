from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from novoya_api.quoting.application.dto import Person


class People(Protocol):
    async def get(self, user_id: UUID) -> Person | None: ...

    async def get_many(self, user_ids: Sequence[UUID]) -> dict[UUID, Person]: ...

    async def search_ids(self, query: str) -> list[UUID]:
        """The ids of the users whose email or name contains `query`."""
        ...
