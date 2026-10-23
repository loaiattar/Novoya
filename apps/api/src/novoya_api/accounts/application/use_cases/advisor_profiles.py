from dataclasses import dataclass

from novoya_api.accounts.application.dto import AgentAdvisorView
from novoya_api.accounts.application.ports.repositories import (
    AdvisorProfileRepository,
    UserRepository,
)
from novoya_api.accounts.domain.advisor_profile import AdvisorProfile, AdvisorService
from novoya_api.accounts.domain.errors import NotAnAgent, UserNotFound
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import UserId
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork

# The agency has a handful of agents: one page holds them all.
AGENTS_MAX = 100


class ListAdvisors:
    """The advisors on the home page (GET /advisors, public)."""

    def __init__(self, profiles: AdvisorProfileRepository) -> None:
        self._profiles = profiles

    async def __call__(self) -> list[AdvisorProfile]:
        return await self._profiles.list_shown()


class ListAgentAdvisors:
    """Every agent with their public profile, if any, for the back office. Admin only."""

    def __init__(self, users: UserRepository, profiles: AdvisorProfileRepository) -> None:
        self._users = users
        self._profiles = profiles

    async def __call__(self) -> list[AgentAdvisorView]:
        agents = await self._users.search(None, Role.AGENT, AGENTS_MAX, 0)
        profiles = await self._profiles.for_users([agent.id for agent in agents])
        return [AgentAdvisorView(agent, profiles.get(agent.id)) for agent in agents]


@dataclass(frozen=True, slots=True)
class UpdateAdvisorProfileCommand:
    """The whole profile, as the admin's form sends it."""

    user_id: UserId
    public_name: str
    title: str | None
    summary: str | None
    services: list[tuple[str | None, str | None]]  # (French, English): one of the two at least
    consent: bool
    shown: bool
    by: UserId  # the signed-in admin, recorded with the agent's agreement


class UpdateAdvisorProfile:
    """An admin fills in an agent's public profile and chooses whether the home page shows it.
    The route checks that the caller is an admin (require_admin)."""

    def __init__(
        self,
        users: UserRepository,
        profiles: AdvisorProfileRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._users = users
        self._profiles = profiles
        self._uow = uow
        self._clock = clock

    async def __call__(self, cmd: UpdateAdvisorProfileCommand) -> AgentAdvisorView:
        user = await self._users.get(cmd.user_id)
        if user is None:
            raise UserNotFound("no user with this id")
        if user.role is not Role.AGENT:
            raise NotAnAgent("only an agent has an advisor profile")

        now = self._clock.now()
        profile = await self._profiles.get_for_user(user.id) or AdvisorProfile.new(user.id, now)
        profile.edit(
            public_name=cmd.public_name,
            title=cmd.title,
            summary=cmd.summary,
            services=[AdvisorService.of(fr, en) for fr, en in cmd.services],
            consent=cmd.consent,
            shown=cmd.shown,
            by=cmd.by,
            now=now,
        )
        await self._profiles.save(profile)
        await self._uow.commit()
        return AgentAdvisorView(user, profile)
