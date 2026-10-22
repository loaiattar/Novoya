from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.shared.domain.errors import InvalidTransition
from novoya_api.wishes.domain.answers import Answers, SelectedTag
from novoya_api.wishes.domain.panel import Panel
from novoya_api.wishes.domain.wish import Destination, Wish, WishStatus
from novoya_api.wishes.infrastructure.db.models import WishModel


def wish_to_entity(row: WishModel) -> Wish:
    answers = None
    if row.start_date is not None:  # saved together with the other answer columns
        answers = Answers(
            selected_tags=tuple(
                SelectedTag(section=item["section"], tag=item["tag"])
                for item in row.selected_tags or []
            ),
            budget_max=row.budget_max,
            currency=row.currency,
            persons=row.persons,
            start_date=row.start_date,
            end_date=row.end_date,
        )
    return Wish(
        id=row.id,
        user_id=row.user_id,
        text=row.text,
        status=WishStatus(row.status),
        destination=(
            Destination(row.destination_country, row.destination_city)
            if row.destination_country
            else None
        ),
        panel=Panel.from_dict(row.panel_json) if row.panel_json else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
        answers=answers,
    )


def wish_columns(wish: Wish) -> dict[str, Any]:
    """The columns that change as the wish moves on; id, user and text never do."""
    answers = wish.answers
    return {
        "destination_country": wish.destination.country if wish.destination else None,
        "destination_city": wish.destination.city if wish.destination else None,
        "status": wish.status.value,
        "panel_json": wish.panel.to_dict() if wish.panel else None,
        "selected_tags": (
            [{"section": t.section, "tag": t.tag} for t in answers.selected_tags]
            if answers
            else None
        ),
        "budget_max": answers.budget_max if answers else None,
        "currency": answers.currency if answers else None,
        "persons": answers.persons if answers else None,
        "start_date": answers.start_date if answers else None,
        "end_date": answers.end_date if answers else None,
        "updated_at": wish.updated_at,
    }


class SqlWishRepository:
    """WishRepository on PostgreSQL. Maps the entity to a row; the use case commits.

    save() updates the row only if its status is still the one this request read: two
    answers sent at once must not both pass the "answered once" rule."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._read_status: dict[UUID, str] = {}

    async def get(self, wish_id: UUID) -> Wish | None:
        row = await self._session.get(WishModel, wish_id)
        if row is None:
            return None
        self._read_status[row.id] = row.status
        return wish_to_entity(row)

    async def list_by_ids(self, ids: Sequence[UUID]) -> list[Wish]:
        if not ids:
            return []
        rows = await self._session.scalars(select(WishModel).where(WishModel.id.in_(ids)))
        found = {row.id: wish_to_entity(row) for row in rows}
        return [found[wish_id] for wish_id in ids if wish_id in found]

    async def add(self, wish: Wish) -> None:
        self._session.add(
            WishModel(
                id=wish.id,
                user_id=wish.user_id,
                text=wish.text,
                created_at=wish.created_at,
                **wish_columns(wish),
            )
        )
        self._read_status[wish.id] = wish.status.value

    async def save(self, wish: Wish) -> None:
        read_status = self._read_status[wish.id]  # KeyError: save() without get() or add()
        result = await self._session.execute(
            update(WishModel)
            .where(WishModel.id == wish.id, WishModel.status == read_status)
            .values(**wish_columns(wish))
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise InvalidTransition("the wish changed meanwhile, reload it")
        self._read_status[wish.id] = wish.status.value

    async def delete_for_user(self, user_id: UUID) -> None:
        """Erase every wish of this user. The caller commits."""
        await self._session.execute(
            delete(WishModel)
            .where(WishModel.user_id == user_id)
            .execution_options(synchronize_session=False)
        )
