"""QuoteNotifier over SMTP: plain text, plus an HTML version with the button. Locally, Mailpit
catches every email: http://localhost:8025."""

import logging
from email.message import EmailMessage
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from novoya_api.quoting.application.dto import QuoteEmail
from novoya_api.quoting.infrastructure.formats import country, day
from novoya_api.shared.domain.value_objects import Locale

logger = logging.getLogger(__name__)

TEMPLATES = Path(__file__).parent / "templates"

# The email only says where to look: no PDF, no price, no partner (docs/ARCHITECTURE.md §5).
TEXTS: dict[Locale, dict[str, str]] = {
    Locale.EN: {
        "subject": "Your quote is ready",
        "hello": "Hello,",
        "hello_name": "Hello {name},",
        "ready": "The offer for your trip is available in your Novoya account.",
        "destination": "Destination",
        "dates": "Dates",
        "range": "{start} to {end}",
        "button": "Log in to see my quote",
        "fallback": "If the button does not work, open this link:",
        "signature": "The Novoya team",
    },
    Locale.FR: {
        "subject": "Votre devis est prêt",
        "hello": "Bonjour,",
        "hello_name": "Bonjour {name},",
        "ready": "L'offre pour votre voyage est disponible dans votre compte Novoya.",
        "destination": "Destination",
        "dates": "Dates",
        "range": "du {start} au {end}",
        "button": "Me connecter pour voir mon devis",
        "fallback": "Si le bouton ne fonctionne pas, ouvrez ce lien :",
        "signature": "L'équipe Novoya",
    },
}

_environment = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(["html"]),
    undefined=StrictUndefined,
)


def _facts(email: QuoteEmail) -> list[tuple[str, str]]:
    """(label, value) for the destination and the dates; a missing one is left out."""
    texts, trip, locale = TEXTS[email.locale], email.trip, email.locale
    facts = []
    place = ", ".join(p for p in (trip.city, country(trip.country, locale)) if p)
    if place:
        facts.append((texts["destination"], place))
    if trip.start_date and trip.end_date:
        start, end = day(trip.start_date, locale), day(trip.end_date, locale)
        facts.append((texts["dates"], texts["range"].format(start=start, end=end)))
    elif trip.start_date:
        facts.append((texts["dates"], day(trip.start_date, locale)))
    return facts


def quote_ready_message(email: QuoteEmail, sender: str) -> EmailMessage:
    texts = TEXTS[email.locale]
    hello = texts["hello_name"].format(name=email.name) if email.name else texts["hello"]
    facts = _facts(email)
    separator = " : " if email.locale is Locale.FR else ": "
    lines = [hello, "", texts["ready"], ""]
    lines += [f"{label}{separator}{value}" for label, value in facts]
    lines += ["", f"{texts['button']}{separator.rstrip()}", email.quote_url, "", texts["signature"]]

    message = EmailMessage()
    message["From"] = sender
    message["To"] = email.to
    message["Subject"] = texts["subject"]
    message.set_content("\n".join(lines))
    html = _environment.get_template("quote_ready.html").render(
        lang=email.locale.value,
        texts=texts,
        hello=hello,
        facts=facts,
        separator=separator,
        quote_url=email.quote_url,
    )
    message.add_alternative(html, subtype="html")
    return message


class SmtpQuoteNotifier:
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

    async def send_quote_ready(self, email: QuoteEmail) -> bool:
        try:
            await aiosmtplib.send(
                quote_ready_message(email, self._sender),
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                start_tls=self._start_tls,
                timeout=10,
            )
        except Exception as error:
            # The quote is already committed: any failure, SMTP or building the message
            # (template, Babel), must give email_sent false, not a 500 the agent cannot retry.
            # Only the error type: SMTP messages can contain the address.
            logger.error("could not send the quote email: %s", type(error).__name__)
            return False
        return True
