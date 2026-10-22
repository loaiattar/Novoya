"""What other modules may use from accounts. Nothing else in accounts may be imported.

- current_user / CurrentUser: the signed-in user (401 if nobody is), as a CurrentUserView
- require_client, require_agent, require_admin: protect a router by role (403 otherwise);
  the admin passes all three. Use them on the router, never test user.role in a route.
- Role
- get_user(user_id) -> UserView (email, name, language), e.g. for the quote PDF and email
- get_users(user_ids) -> {user_id: UserView}, the same for a whole page of an admin list
- search_user_ids(query) -> the ids of the users whose email or name contains `query`, so
  an admin list in another module can search by client
- count_users_by_role() -> {role: count}: every role, 0 when nobody has it, for the admin
  dashboard. Counts only.
- delete_expired_sign_ins(): deletes the sessions past their 30 days and the expired email
  links, for the API's startup (sign-ins and new links do it too). The caller commits.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.application.dto import CurrentUserView
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import UserId
from novoya_api.accounts.infrastructure.db.repositories import (
    SqlOneTimeTokenRepository,
    SqlSessionRepository,
    SqlUserRepository,
)
from novoya_api.accounts.presentation.http.dependencies import (
    CurrentUser,
    current_user,
    require_admin,
    require_agent,
    require_client,
)
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.shared.infrastructure.system_clock import SystemClock

__all__ = [
    "CurrentUser",
    "CurrentUserView",
    "Role",
    "UserView",
    "count_users_by_role",
    "current_user",
    "delete_expired_sign_ins",
    "get_user",
    "get_users",
    "require_admin",
    "require_agent",
    "require_client",
    "search_user_ids",
]

# Past this many matches, the query is too broad to be a useful filter: the newest win, and the
# rest is dropped without a sign. Fine at the agency's size; a page would say "refine".
SEARCH_CAP = 500


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


async def get_users(user_ids: Sequence[UUID], *, session: AsyncSession) -> dict[UUID, UserView]:
    """The users with these ids, keyed by id. Missing ids are omitted."""
    users = await SqlUserRepository(session).list_by_ids(list(set(user_ids)))
    return {
        user.id.value: UserView(user.id.value, user.email.value, user.name, user.locale)
        for user in users
    }


async def search_user_ids(query: str, *, session: AsyncSession) -> list[UUID]:
    """The ids of the users whose email or name contains `query`, newest first, at most
    SEARCH_CAP. For admins only: the caller's router must require the admin role."""
    users = await SqlUserRepository(session).search(query, None, SEARCH_CAP, 0)
    return [user.id.value for user in users]


async def count_users_by_role(*, session: AsyncSession) -> dict[str, int]:
    """How many accounts have each role, disabled ones too. For admins only: the caller's
    router must require the admin role."""
    found = await SqlUserRepository(session).count_by_role()
    return {role.value: found.get(role.value, 0) for role in Role}


async def delete_expired_sign_ins(*, session: AsyncSession) -> None:
    """Delete the sessions past their absolute expiry (30 days) and the expired email links.
    Sign-ins and new links do it as they come; this covers a quiet spell. The caller commits."""
    now = SystemClock().now()
    await SqlSessionRepository(session).delete_expired(now)
    await SqlOneTimeTokenRepository(session).delete_expired(now)
