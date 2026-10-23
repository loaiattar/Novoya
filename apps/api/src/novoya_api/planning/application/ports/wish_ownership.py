from typing import Protocol
from uuid import UUID


class WishOwnership(Protocol):
    """The wish's owner, so a plan is only shown or quoted to the client who asked."""

    async def owner_id(self, wish_id: UUID) -> UUID | None: ...
