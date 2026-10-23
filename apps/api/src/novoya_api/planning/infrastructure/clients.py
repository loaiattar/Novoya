from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.public import get_user
from novoya_api.planning.application.dto import ClientContact


class AccountClients:
    """ClientDirectory through accounts.public, in the request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def contact(self, user_id: UUID) -> ClientContact | None:
        user = await get_user(user_id, session=self._session)
        if user is None:
            return None
        return ClientContact(user.email, user.name, user.locale)
