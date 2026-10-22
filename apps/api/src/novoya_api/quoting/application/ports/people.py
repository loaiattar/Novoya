from typing import Protocol
from uuid import UUID

from novoya_api.quoting.application.dto import Person


class People(Protocol):
    async def get(self, user_id: UUID) -> Person | None: ...
