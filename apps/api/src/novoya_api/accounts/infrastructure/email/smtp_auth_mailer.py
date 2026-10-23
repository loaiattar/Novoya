"""AuthMailer over SMTP. Locally, Mailpit catches every email: http://localhost:8025."""

import logging
from email.message import EmailMessage

import aiosmtplib

from novoya_api.accounts.domain.value_objects import Email
from novoya_api.shared.domain.value_objects import Locale

logger = logging.getLogger(__name__)

# (subject, body) per email and language. The body is plain text; {link} is filled in.
MESSAGES: dict[str, dict[Locale, tuple[str, str]]] = {
    "email_verification": {
        Locale.EN: (
            "Confirm your email address",
            "Welcome to Novoya!\n\nConfirm your email address with this link, valid for "
            "24 hours:\n{link}\n\nIf you did not create an account, ignore this email.",
        ),
        Locale.FR: (
            "Confirmez votre adresse e-mail",
            "Bienvenue sur Novoya !\n\nConfirmez votre adresse e-mail avec ce lien, valable "
            "24 heures :\n{link}\n\nSi vous n'avez pas créé de compte, ignorez cet e-mail.",
        ),
    },
    "password_reset": {
        Locale.EN: (
            "Reset your password",
            "Choose a new password with this link, valid for 30 minutes:\n{link}\n\n"
            "If you did not ask for it, ignore this email: your password stays the same.",
        ),
        Locale.FR: (
            "Réinitialisez votre mot de passe",
            "Choisissez un nouveau mot de passe avec ce lien, valable 30 minutes :\n{link}\n\n"
            "Si vous ne l'avez pas demandé, ignorez cet e-mail : votre mot de passe ne change pas.",
        ),
    },
    "password_changed": {
        Locale.EN: (
            "Your password was changed",
            "The password of your Novoya account was just changed.\n\n"
            "If it was not you, reset it now from the sign-in page.",
        ),
        Locale.FR: (
            "Votre mot de passe a été modifié",
            "Le mot de passe de votre compte Novoya vient d'être modifié.\n\n"
            "Si ce n'est pas vous, réinitialisez-le depuis la page de connexion.",
        ),
    },
}


class SmtpAuthMailer:
    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        frontend_url: str,
        username: str | None = None,
        password: str | None = None,
        start_tls: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._start_tls = start_tls
        self._sender = sender
        self._frontend_url = frontend_url.rstrip("/")

    async def send_email_verification(self, to: Email, locale: Locale, token: str) -> None:
        link = f"{self._frontend_url}/verify-email?token={token}"
        await self._send("email_verification", to, locale, link)

    async def send_password_reset(self, to: Email, locale: Locale, token: str) -> None:
        link = f"{self._frontend_url}/reset-password?token={token}"
        await self._send("password_reset", to, locale, link)

    async def send_password_changed_notice(self, to: Email, locale: Locale) -> None:
        await self._send("password_changed", to, locale, link="")

    async def _send(self, kind: str, to: Email, locale: Locale, link: str) -> None:
        subject, body = MESSAGES[kind][locale]
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = to.value
        message["Subject"] = subject
        message.set_content(body.format(link=link))
        try:
            await aiosmtplib.send(
                message,
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                start_tls=self._start_tls,
                timeout=10,
            )
        except (aiosmtplib.SMTPException, OSError) as error:
            # The account change is already committed; the user can ask for a new link.
            # Only the error type: SMTP messages can contain the address (plan §12.9).
            logger.error("could not send the %s email: %s", kind, type(error).__name__)
