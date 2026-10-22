"""What other modules may use from wishes. Nothing else in wishes may be imported.

- owner_id(wish_id) -> the user who sent the wish, or None when there is none
- trips(wish_ids) -> text, destination, dates, travellers and budget for those wishes

Planned:
- mark_planned(wish_id)
- delete_for_user(user_id)
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository


@dataclass(frozen=True)
class WishTrip:
    """The wish as another module shows it on the agent's queue. Missing answers stay None."""

    wish_id: UUID
    text: str
    country: str | None
    city: str | None
    budget_max: Decimal | None
    currency: str | None
    persons: int | None
    start_date: date | None
    end_date: date | None


async def owner_id(wish_id: UUID, *, session: AsyncSession) -> UUID | None:
    """The user who sent this wish. None when the wish is missing."""
    wish = await SqlWishRepository(session).get(wish_id)
    return None if wish is None else wish.user_id


async def trips(wish_ids: Sequence[UUID], *, session: AsyncSession) -> dict[UUID, WishTrip]:
    """Wish text, place, dates, travellers and budget, keyed by wish id. Missing ids are omitted."""
    found: dict[UUID, WishTrip] = {}
    for wish in await SqlWishRepository(session).list_by_ids(wish_ids):
        answers = wish.answers
        destination = wish.destination
        found[wish.id] = WishTrip(
            wish_id=wish.id,
            text=wish.text,
            country=destination.country if destination else None,
            city=destination.city if destination else None,
            budget_max=answers.budget_max if answers else None,
            currency=answers.currency if answers else None,
            persons=answers.persons if answers else None,
            start_date=answers.start_date if answers else None,
            end_date=answers.end_date if answers else None,
        )
    return found


async def delete_for_user(user_id: UUID, *, session: AsyncSession) -> None:
    """Erase every wish of this user. Plans must be erased first. The caller commits."""
    await SqlWishRepository(session).delete_for_user(user_id)
