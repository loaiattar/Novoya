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


class ChangeLocale:
    """The signed-in user picks their language (PATCH /me). Answers like GET /me."""

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

    async def __call__(self, user_id: UserId, locale: Locale) -> AccountView:
        user = await self._users.get(user_id)
        if user is None:
            raise UserNotFound("no user with this id")
        if user.locale is not locale:
            user.change_locale(locale)
            await self._users.save(user)
            await self._uow.commit()
        return await self._get_account(user_id)
