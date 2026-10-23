"""RequestNotifier over SMTP, after the quote email (quoting/infrastructure/email, #143): plain
text, in the client's language. Locally, Mailpit catches every email: http://localhost:8025."""

import logging
from email.message import EmailMessage

import aiosmtplib

from novoya_api.planning.application.dto import RequestReceivedEmail
from novoya_api.shared.domain.value_objects import Locale

logger = logging.getLogger(__name__)

# No price and no partner here (docs/ARCHITECTURE.md §5): only that the agency has the trip,
# when to expect the answer, and where to follow it.
TEXTS: dict[Locale, dict[str, str]] = {
    Locale.EN: {
        "subject": "The agency received your trip",
        "hello": "Hello,",
        "hello_name": "Hello {name},",
        "received_one": "The agency received your trip. An advisor will answer within 1 day.",
        "received": "The agency received your trip. An advisor will answer within {days} days.",
        "next": "They check each day of your trip, negotiate the prices and send you a quote.",
        "link": "Follow your trip:",
        "signature": "The Novoya team",
    },
    Locale.FR: {
        "subject": "L'agence a bien reçu votre voyage",
        "hello": "Bonjour,",
        "hello_name": "Bonjour {name},",
        "received_one": (
            "L'agence a bien reçu votre voyage. Un conseiller vous répondra sous 1 jour."
        ),
        "received": (
            "L'agence a bien reçu votre voyage. Un conseiller vous répondra sous {days} jours."
        ),
        "next": "Il vérifie chaque journée, négocie les prix et vous envoie un devis.",
        "link": "Suivre votre voyage :",
        "signature": "L'équipe Novoya",
    },
}


def request_received_message(email: RequestReceivedEmail, sender: str) -> EmailMessage:
    texts = TEXTS[email.locale]
    hello = texts["hello_name"].format(name=email.name) if email.name else texts["hello"]
    lines = [
        hello,
        "",
        texts["received_one" if email.answer_days == 1 else "received"].format(
            days=email.answer_days
        ),
        texts["next"],
        "",
        texts["link"],
        email.plan_url,
        "",
        texts["signature"],
    ]
    message = EmailMessage()
    message["From"] = sender
    message["To"] = email.to
    message["Subject"] = texts["subject"]
    message.set_content("\n".join(lines))
    return message


class SmtpRequestNotifier:
    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
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

    async def send_request_received(self, email: RequestReceivedEmail) -> bool:
        try:
            await aiosmtplib.send(
                request_received_message(email, self._sender),
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                start_tls=self._start_tls,
                timeout=10,
            )
        except Exception as error:
            # The request is already committed: a failed email must not turn it into a 500.
            # Only the error type: SMTP messages can contain the address.
            logger.error("could not send the request email: %s", type(error).__name__)
            return False
        return True
