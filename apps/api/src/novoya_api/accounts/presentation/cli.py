"""Server commands of the accounts module.

grant-role gives a role to an existing account, for example a super admin: the API never gives
that role. It needs access to the server:

    uv run python -m novoya_api.accounts.presentation.cli grant-role --email a@b.c --role admin
    docker compose exec api python -m novoya_api.accounts.presentation.cli grant-role ...

Only this command gives or takes the super admin role. The role change is logged with source
"cmd_grant_role".
"""

import argparse
import asyncio
import sys

from novoya_api.accounts.application.use_cases.change_user_role import ChangeUserRoleCommand
from novoya_api.accounts.domain.actor import GRANT_ROLE_COMMAND
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import Email
from novoya_api.accounts.presentation.http.dependencies import (
    build_change_user_role,
    close_db,
    open_db_session,
)
from novoya_api.shared.domain.errors import DomainError


async def grant_role(email: str, role: Role) -> None:
    try:
        async with open_db_session() as session:
            change_user_role = build_change_user_role(session)
            command = ChangeUserRoleCommand(Email(email), role, by=GRANT_ROLE_COMMAND)
            user = await change_user_role(command)
    finally:
        await close_db()
    print(f"{user.email} is now {user.role}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="novoya_api.accounts.presentation.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    grant = commands.add_parser("grant-role", help="give a role to an existing account")
    grant.add_argument("--email", required=True)
    grant.add_argument("--role", required=True, choices=[role.value for role in Role])
    args = parser.parse_args(argv)

    try:
        asyncio.run(grant_role(args.email, Role(args.role)))
    except DomainError as error:
        print(f"error: {error.code}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
