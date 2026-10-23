from novoya_api.wishes.application.dto import AdminWishView, Client
from novoya_api.wishes.application.ports.clients import Clients
from novoya_api.wishes.application.ports.wish_repository import (
    ADMIN_CAP,
    ADMIN_PAGE,
    WishRepository,
)
from novoya_api.wishes.domain.wish import Wish, WishStatus


class ListAdminWishes:
    """Every client's wishes, last changed first, for the admin overview. The search matches
    the client's email or name, or the destination's country or city."""

    def __init__(self, wishes: WishRepository, clients: Clients) -> None:
        self._wishes = wishes
        self._clients = clients

    async def __call__(
        self,
        status: WishStatus | None = None,
        query: str | None = None,
        *,
        limit: int = ADMIN_PAGE,
        offset: int = 0,
    ) -> list[AdminWishView]:
        query = query.strip() if query else None
        user_ids = await self._clients.search_ids(query) if query else []
        wishes = await self._wishes.search(
            status, query, user_ids, limit=min(max(limit, 1), ADMIN_CAP), offset=max(offset, 0)
        )
        clients = await self._clients.get_many([wish.user_id for wish in wishes])
        return [_view(wish, clients.get(wish.user_id)) for wish in wishes]


def _view(wish: Wish, client: Client | None) -> AdminWishView:
    destination, answers = wish.destination, wish.answers
    return AdminWishView(
        id=wish.id,
        status=wish.status.value,
        text=wish.text,
        country=destination.country if destination else None,
        city=destination.city if destination else None,
        persons=answers.persons if answers else None,
        start_date=answers.start_date if answers else None,
        end_date=answers.end_date if answers else None,
        created_at=wish.created_at,
        updated_at=wish.updated_at,
        client=client,
    )
