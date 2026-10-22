"""What other modules may use from accounts. Nothing else in accounts may be imported.

- current_user / CurrentUser: the signed-in user (401 if nobody is), as a CurrentUserView
- require_client, require_agent, require_admin: protect a router by role (403 otherwise);
  the admin passes all three. Use them on the router, never test user.role in a route.
- Role
- get_user(user_id) -> UserView (email, name, language), e.g. for the quote PDF and email
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.application.dto import CurrentUserView
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import UserId
from novoya_api.accounts.infrastructure.db.repositories import SqlUserRepository
from novoya_api.accounts.presentation.http.dependencies import (
    CurrentUser,
    current_user,
    require_admin,
    require_agent,
    require_client,
)
from novoya_api.shared.domain.value_objects import Locale

__all__ = [
    "CurrentUser",
    "CurrentUserView",
    "Role",
    "UserView",
    "current_user",
    "get_user",
    "require_admin",
    "require_agent",
    "require_client",
]


@dataclass(frozen=True)
class UserView:
    """A user as another module shows them: who to write to and in which language."""

    user_id: UUID
    email: str
    name: str | None
    locale: Locale


async def get_user(user_id: UUID, *, session: AsyncSession) -> UserView | None:
    """The user's email, name and language. None when there is no such user."""
    user = await SqlUserRepository(session).get(UserId(user_id))
    if user is None:
        return None
    return UserView(user.id.value, user.email.value, user.name, user.locale)
