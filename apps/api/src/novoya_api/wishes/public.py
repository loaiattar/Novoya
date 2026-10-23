"""What other modules may use from wishes. Nothing else in wishes may be imported.

- owner_id(wish_id, lock_for=None) -> the user who sent the wish, or None when there is
  none. lock_for=user locks the row FOR SHARE when that user owns it, so a removal waits
- lock_for_user(user_id) -> locks this user's wishes FOR UPDATE in id order. Call it first
  in a transaction that also locks their plans or quotes (DELETE /me)
- trips(wish_ids) -> text, destination, dates, travellers, budget and tags for those wishes
- ids_for_user(user_id) -> the ids of this user's wishes
- search_ids(query, user_ids) -> the ids of the wishes whose country or city contains `query`,
  or that one of `user_ids` sent (accounts.public.search_user_ids finds them), for the admin
  overview of plans and quotes
- preferences(user_id) -> the "section:tag" this user picked on the panels of their wishes,
  each once, newest wish first
- delete_for_user(user_id) -> erases every wish of this user. Erase their plans first
  (plans.wish_id has no cascade).
- wishes_for_user(user_id) -> this user's wishes, newest first, with their status, place and
  dates

Planned:
- mark_planned(wish_id)
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.wishes.application.use_cases.preferences import group_preferences
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository

# The wishes a search may match, newest first: past it the query is too broad to filter, and
# the rest is dropped without a sign. Fine at the agency's size; a page would say "refine".
SEARCH_CAP = 1000


@dataclass(frozen=True)
class WishTrip:
    """The wish as another module shows it on the agent's queue. Missing answers stay None."""

    wish_id: UUID
    user_id: UUID  # the client who sent it
    text: str
    country: str | None
    city: str | None
    budget_max: Decimal | None
    currency: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    tags: tuple[str, ...] = ()  # "section:tag", what the client clicked


@dataclass(frozen=True)
class UserWish:
    """One wish in its client's own list: where, when, and how far it has got."""

    wish_id: UUID
    text: str
    status: str  # draft, not_covered, panel_shown, answered or planned
    country: str | None
    city: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None
    created_at: datetime


async def owner_id(
    wish_id: UUID, *, session: AsyncSession, lock_for: UUID | None = None
) -> UUID | None:
    """The user who sent this wish. None when the wish is missing. With lock_for, and only
    when that user owns the wish, its row stays locked FOR SHARE until the caller's
    transaction ends, so a preference removal on it waits (planning's quote request)."""
    repository = SqlWishRepository(session)
    if lock_for is not None and await repository.owner_id_for_share(wish_id, lock_for):
        return lock_for
    wish = await repository.get(wish_id)
    return None if wish is None else wish.user_id


async def lock_for_user(user_id: UUID, *, session: AsyncSession) -> None:
    """Lock every wish of this user (FOR UPDATE, in id order) until the caller's transaction
    ends. DELETE /me calls it first, so it takes the wishes before their quotes and plans,
    in the same order as a quote request or a preference removal: no deadlock."""
    await SqlWishRepository(session).lock_for_user(user_id)


async def trips(wish_ids: Sequence[UUID], *, session: AsyncSession) -> dict[UUID, WishTrip]:
    """Wish text, place, dates, travellers, budget and tags, keyed by wish id. Missing ids are
    omitted."""
    found: dict[UUID, WishTrip] = {}
    for wish in await SqlWishRepository(session).list_by_ids(wish_ids):
        answers = wish.answers
        destination = wish.destination
        found[wish.id] = WishTrip(
            wish_id=wish.id,
            user_id=wish.user_id,
            text=wish.text,
            country=destination.country if destination else None,
            city=destination.city if destination else None,
            budget_max=answers.budget_max if answers else None,
            currency=answers.currency if answers else None,
            persons=answers.persons if answers else None,
            start_date=answers.start_date if answers else None,
            end_date=answers.end_date if answers else None,
            tags=(
                tuple(f"{tag.section}:{tag.tag}" for tag in answers.selected_tags)
                if answers
                else ()
            ),
        )
    return found


async def ids_for_user(user_id: UUID, *, session: AsyncSession) -> list[UUID]:
    """The ids of this user's wishes, for example to erase their plans first."""
    return await SqlWishRepository(session).ids_for_user(user_id)


async def search_ids(query: str, user_ids: Sequence[UUID], *, session: AsyncSession) -> list[UUID]:
    """The ids of the wishes whose country or city contains `query`, or that one of `user_ids`
    sent. The caller finds the users: importing accounts here would loop, since accounts
    erases wishes. For admins only: the caller's router must require the admin role."""
    wishes = await SqlWishRepository(session).search(None, query, user_ids, limit=SEARCH_CAP)
    return [wish.id for wish in wishes]


async def preferences(user_id: UUID, *, session: AsyncSession) -> tuple[str, ...]:
    """The "section:tag" this user picked on their wishes' panels, each once, newest first."""
    wishes = await SqlWishRepository(session).list_for_user(user_id)
    found = group_preferences(wishes, locked=set())
    return tuple(f"{section.id}:{tag.id}" for section in found for tag in section.tags)


async def delete_for_user(user_id: UUID, *, session: AsyncSession) -> None:
    """Erase every wish of this user. Plans must be erased first. The caller commits."""
    await SqlWishRepository(session).delete_for_user(user_id)


async def wishes_for_user(user_id: UUID, *, session: AsyncSession) -> list[UserWish]:
    """This user's wishes, newest first, for their list of trips."""
    wishes = await SqlWishRepository(session).list_for_user(user_id)
    return [
        UserWish(
            wish_id=wish.id,
            text=wish.text,
            status=wish.status.value,
            country=wish.destination.country if wish.destination else None,
            city=wish.destination.city if wish.destination else None,
            persons=wish.answers.persons if wish.answers else None,
            start_date=wish.answers.start_date if wish.answers else None,
            end_date=wish.answers.end_date if wish.answers else None,
            created_at=wish.created_at,
        )
        for wish in wishes
    ]
