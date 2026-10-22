"""The quote PDF: a Jinja2 HTML template rendered with WeasyPrint, in English or French."""

import base64
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from babel.numbers import format_currency
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup
from weasyprint import HTML
from weasyprint.urls import URLFetcher

from novoya_api.quoting.application.dto import QuoteDocument
from novoya_api.quoting.infrastructure.formats import country as _country
from novoya_api.quoting.infrastructure.formats import day as _day
from novoya_api.shared.domain.value_objects import Locale

TEMPLATES = Path(__file__).parent / "templates"
# Novoya is the project; the quote comes from the agency. Its name, website and email are the
# confirmed values of apps/web/brand/agency.json; the phone and logo.svg were given by the
# agency on 2026-10-22 (agency.json still marks the phone to_check until #109). The API image
# cannot read apps/web, so they are copied here: change both places together.
AGENCY = {
    "name": "DÉTOUR Voyages",
    "website": "www.detour-voyages.fr",
    "email": "contact@detour-voyages.fr",
    "phone": "+33 2 40 00 00 00",
}
LOGO = (
    "data:image/svg+xml;base64," + base64.b64encode((TEMPLATES / "logo.svg").read_bytes()).decode()
)


def _font_face(weight: str, style: str, file: str) -> str:
    data = base64.b64encode((TEMPLATES / "fonts" / file).read_bytes()).decode()
    return (
        f'@font-face {{ font-family: "Liberation Sans"; font-weight: {weight}; '
        f'font-style: {style}; src: url("data:font/ttf;base64,{data}"); }}'
    )


# The font travels with the template (SIL OFL, fonts/LICENSE): the PDF looks the same on a
# laptop, in CI and on the server, whatever fonts the host has. Only the glyphs used are
# embedded in the PDF.
FONTS_CSS = Markup(
    "\n".join(
        (
            _font_face("normal", "normal", "LiberationSans-Regular.ttf"),
            _font_face("bold", "normal", "LiberationSans-Bold.ttf"),
            _font_face("normal", "italic", "LiberationSans-Italic.ttf"),
        )
    )
)

LABELS: dict[Locale, dict[str, str]] = {
    Locale.EN: {
        "quote": "Quote",
        "number": "Number",
        "issued": "Issued on",
        "valid_until": "Valid until",
        "client": "Client",
        "your_agent": "Your travel agent",
        "destination": "Destination",
        "dates": "Dates",
        "travellers": "Travellers",
        "your_wish": "Your wish",
        "your_trip": "Your trip, day by day",
        "day": "Day",
        "item": "What is booked",
        "quantity": "Qty",
        "price": "Amount",
        "extra": "Extra",
        "included": "Included",
        "unavailable": "No longer listed",
        "total": "Total",
        "your_budget": "Your maximum budget",
        "not_included_title": "Not included",
        "not_included": "Flights, meals and drinks not listed above, tips and travel insurance.",
        "how_to_answer_title": "How to answer",
        "how_to_answer": "Sign in to your DÉTOUR account to accept or reject this quote "
        "before {date}. After that date, the prices may change.",
        "questions": "A question? Write to your travel agent:",
        "or_call": "or call the agency:",
    },
    Locale.FR: {
        "quote": "Devis",
        "number": "Numéro",
        "issued": "Émis le",
        "valid_until": "Valable jusqu'au",
        "client": "Client",
        "your_agent": "Votre conseiller voyage",
        "destination": "Destination",
        "dates": "Dates",
        "travellers": "Voyageurs",
        "your_wish": "Votre souhait",
        "your_trip": "Votre voyage, jour par jour",
        "day": "Jour",
        "item": "Prestation réservée",
        "quantity": "Qté",
        "price": "Montant",
        "extra": "Option",
        "included": "Inclus",
        "unavailable": "Plus au catalogue",
        "total": "Total",
        "your_budget": "Votre budget maximum",
        "not_included_title": "Non compris",
        "not_included": "Les vols, les repas et boissons non indiqués ci-dessus, les "
        "pourboires et l'assurance voyage.",
        "how_to_answer_title": "Comment répondre",
        "how_to_answer": "Connectez-vous à votre compte DÉTOUR pour accepter ou refuser ce "
        "devis avant le {date}. Après cette date, les prix peuvent changer.",
        "questions": "Une question ? Écrivez à votre conseiller :",
        "or_call": "ou appelez l'agence :",
    },
}


class WeasyPrintRenderer:
    """QuoteRenderer with Jinja2 and WeasyPrint. Euros and dates in the quote's language."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(TEMPLATES),
            autoescape=select_autoescape(["html"]),
            undefined=StrictUndefined,
        )

    def html(self, document: QuoteDocument) -> str:
        locale = document.quote.locale
        env = self._env.overlay()
        env.filters["money"] = lambda amount: _money(amount, locale)
        env.filters["day"] = lambda value: _day(value, locale)
        plan = document.plan
        return env.get_template("quote.html").render(
            locale=locale.value,
            t=LABELS[locale],
            agency=AGENCY,
            logo=LOGO,
            fonts_css=FONTS_CSS,
            quote=document.quote,
            plan=plan,
            items=[
                {
                    "day": item.day,
                    "date": _date_of_day(plan.start_date, item.day),
                    "title": item.title,
                    "description": item.description,
                    "quantity": item.quantity,
                    "price": item.price,
                }
                for item in plan.items
            ],
            client=document.client,
            agent=document.agent,
            destination=", ".join(
                part for part in (plan.city, _country(plan.country, locale)) if part
            )
            or "–",
            tags=[_tag_label(tag) for tag in plan.tags],
            answer_url=document.answer_url,
        )

    def render(self, document: QuoteDocument) -> bytes:
        # The CSS is inline and the logo a data: URI, so the quote fetches nothing else: text
        # a client or a partner wrote can never read a local file or call a server.
        fetcher = URLFetcher(allowed_protocols={"data"})
        return HTML(
            string=self.html(document), base_url=str(TEMPLATES), url_fetcher=fetcher
        ).write_pdf()


def _money(amount: Decimal, locale: Locale) -> str:
    return format_currency(amount, "EUR", locale=locale.value)


def _date_of_day(start: date | None, day: int) -> date | None:
    """Day 1 is the departure."""
    return start + timedelta(days=day - 1) if start else None


def _tag_label(tag: str) -> str:
    """ "style:beach-bars" -> "beach bars": the client clicked the tag, not the section."""
    return tag.rpartition(":")[2].replace("-", " ").replace("_", " ")
