from typing import Protocol

from novoya_api.accounts.domain.value_objects import Email
from novoya_api.shared.domain.value_objects import Locale


class AuthMailer(Protocol):
    """The emails of the accounts module, in the user's language.

    `token` is the raw one-time token: the adapter builds the link to the frontend.
    """

    async def send_email_verification(self, to: Email, locale: Locale, token: str) -> None: ...

    async def send_password_reset(self, to: Email, locale: Locale, token: str) -> None: ...

    async def send_password_changed_notice(self, to: Email, locale: Locale) -> None: ...
