from typing import Protocol
from uuid import UUID

from novoya_api.planning.application.dto import ClientContact


class ClientDirectory(Protocol):
    """The client's email, name and language, for the confirmation email."""

    async def contact(self, user_id: UUID) -> ClientContact | None: ...
