from novoya_api.accounts.application.dto import AccountView
from novoya_api.accounts.application.ports.repositories import (
    OAuthIdentityRepository,
    PasswordCredentialRepository,
    UserRepository,
)
from novoya_api.accounts.domain.errors import UserNotFound
from novoya_api.accounts.domain.value_objects import UserId


class GetAccount:
    """A user with the ways they can sign in. Used by GET /me and the admin pages."""

    def __init__(
        self,
        users: UserRepository,
        credentials: PasswordCredentialRepository,
        identities: OAuthIdentityRepository,
    ) -> None:
        self._users = users
        self._credentials = credentials
        self._identities = identities

    async def __call__(self, user_id: UserId) -> AccountView:
        user = await self._users.get(user_id)
        if user is None:
            raise UserNotFound("no user with this id")
        credential = await self._credentials.get(user_id)
        return AccountView(
            user,
            has_password=credential is not None,
            has_google="google" in await self._identities.providers_for_user(user_id),
        )
