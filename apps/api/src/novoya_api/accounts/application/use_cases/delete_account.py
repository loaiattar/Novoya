from novoya_api.accounts.application.ports.repositories import UserRepository
from novoya_api.accounts.application.ports.user_data import UserDataEraser
from novoya_api.accounts.domain.errors import StaffAccountDeletion, UserNotFound
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import UserId
from novoya_api.shared.application.unit_of_work import UnitOfWork


class DeleteAccount:
    """A client erases their account and everything Novoya stored about them (DELETE /me,
    GDPR). One commit: their data and the account go together or not at all."""

    def __init__(self, users: UserRepository, data: UserDataEraser, uow: UnitOfWork) -> None:
        self._users = users
        self._data = data
        self._uow = uow

    async def __call__(self, user_id: UserId) -> None:
        user = await self._users.get(user_id)
        if user is None:
            raise UserNotFound("no user with this id")
        if user.role is not Role.CLIENT:
            raise StaffAccountDeletion("only a client can delete their own account")
        await self._data.erase(user_id)
        await self._users.delete(user_id)
        await self._uow.commit()
