from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from novoya_api.wishes.domain.wish import Wish, WishStatus

ADMIN_PAGE = 50
ADMIN_CAP = 100


class WishRepository(Protocol):
    async def add(self, wish: Wish) -> None: ...

    async def get(self, wish_id: UUID) -> Wish | None: ...

    async def list_for_user(self, user_id: UUID, *, lock: bool = False) -> list[Wish]:
        """This user's wishes, newest first. save() works on each of them, as after get().
        With lock, the rows stay locked until the transaction ends (SELECT ... FOR UPDATE)."""
        ...

    async def save(self, wish: Wish) -> None:
        """Raises InvalidTransition if another request changed the wish since get()."""
        ...

    async def search(
        self,
        status: WishStatus | None,
        query: str | None,
        user_ids: Sequence[UUID],
        *,
        limit: int = ADMIN_PAGE,
        offset: int = 0,
    ) -> list[Wish]:
        """Every client's wishes, last changed first. With a query: the wishes whose country or
        city contains it, or that one of `user_ids` sent."""
        ...
