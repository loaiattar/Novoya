from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import get_user
from novoya_api.quoting.application.dto import Person


class AccountPeople:
    """People through accounts.public, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> Person | None:
        user = await get_user(user_id, session=self._session)
        if user is None:
            return None
        return Person(user.user_id, user.name, user.email, user.locale)
