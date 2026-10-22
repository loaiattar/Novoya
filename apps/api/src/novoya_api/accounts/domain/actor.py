from dataclasses import dataclass

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import UserId


@dataclass(frozen=True, slots=True)
class AdminActor:
    """A signed-in user changing a role or a status through the API. Their role says what
    they may change: the entity checks it again, whatever the route let through."""

    user_id: UserId
    role: Role


@dataclass(frozen=True, slots=True)
class ServerCommand:
    """The grant-role command. Whoever runs it has access to the server: it is the only one
    that gives the super admin role."""


GRANT_ROLE_COMMAND = ServerCommand()

# Who changes a user's role. Always named: there is no "no caller" that means the command.
RoleActor = AdminActor | ServerCommand
