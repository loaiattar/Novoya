from dataclasses import dataclass

from novoya_api.accounts.application.dto import AccountView
from novoya_api.accounts.application.ports.repositories import (
    OAuthIdentityRepository,
    PasswordCredentialRepository,
    UserRepository,
)
from novoya_api.accounts.application.use_cases.get_account import GetAccount
from novoya_api.accounts.domain.errors import UserNotFound
from novoya_api.accounts.domain.value_objects import UserId
from novoya_api.shared.application.unit_of_work import UnitOfWork
from novoya_api.shared.domain.value_objects import Locale


@dataclass(frozen=True, slots=True)
class UpdateMeCommand:
    """What the user changes about themselves. None leaves a field as it is."""

    first_name: str | None = None
    last_name: str | None = None
    locale: Locale | None = None


class UpdateMe:
    """The signed-in user changes their first name, last name or language (PATCH /me).
    The email is the sign-in identity and is not changed here. Answers like GET /me."""

    def __init__(
        self,
        users: UserRepository,
        credentials: PasswordCredentialRepository,
        identities: OAuthIdentityRepository,
        uow: UnitOfWork,
    ) -> None:
        self._users = users
        self._uow = uow
        self._get_account = GetAccount(users, credentials, identities)

    async def __call__(self, user_id: UserId, command: UpdateMeCommand) -> AccountView:
        user = await self._users.get(user_id)
        if user is None:
            raise UserNotFound("no user with this id")
        before = (user.first_name, user.last_name, user.name, user.locale)
        user.rename(command.first_name, command.last_name)
        if command.locale is not None:
            user.change_locale(command.locale)
        if (user.first_name, user.last_name, user.name, user.locale) != before:
            await self._users.save(user)
            await self._uow.commit()
        return await self._get_account(user_id)
