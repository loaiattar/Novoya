from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.domain.value_objects import UserId
from novoya_api.planning.public import delete_for_user as delete_plans
from novoya_api.quoting.public import delete_for_user as delete_quotes
from novoya_api.wishes.public import delete_for_user as delete_wishes
from novoya_api.wishes.public import lock_for_user as lock_wishes


class ModuleDataEraser:
    """UserDataEraser through the other modules' public.py, in the request's session.

    The order matters: a quote points to its plan and a plan to its wish, with no cascade."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def erase(self, user_id: UserId) -> None:
        # Wishes first, as a quote request or a preference removal does: no deadlock.
        await lock_wishes(user_id.value, session=self._session)
        await delete_quotes(user_id.value, session=self._session)
        await delete_plans(user_id.value, session=self._session)
        await delete_wishes(user_id.value, session=self._session)
