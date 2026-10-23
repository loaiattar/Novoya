from dataclasses import dataclass
from uuid import UUID

from novoya_api.accounts.domain.advisor_profile import AdvisorProfile
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import User
from novoya_api.accounts.domain.value_objects import Email, SessionToken, UserId
from novoya_api.shared.domain.value_objects import Locale


@dataclass(frozen=True, slots=True)
class ClientInfo:
    """What we know about the browser making the request."""

    ip_address: str | None  # only for rate limits, in memory; never stored
    user_agent: str | None
    current_token: SessionToken | None  # the session cookie the request already carries


@dataclass(frozen=True, slots=True)
class CurrentUserView:
    """The signed-in user, as other modules see them."""

    user_id: UserId
    email: Email
    name: str | None
    role: Role
    locale: Locale
    session_id: UUID  # the current session, e.g. to keep it open when the password changes

    @classmethod
    def of(cls, user: User, session_id: UUID) -> "CurrentUserView":
        return cls(user.id, user.email, user.name, user.role, user.locale, session_id)


@dataclass(frozen=True, slots=True)
class AccountView:
    """A user with what GET /me and the admin pages show."""

    user: User
    has_password: bool
    has_google: bool = False


@dataclass(frozen=True, slots=True)
class AgentAdvisorView:
    """An agent and their public profile, for the back office. None until an admin fills it."""

    user: User
    profile: AdvisorProfile | None
