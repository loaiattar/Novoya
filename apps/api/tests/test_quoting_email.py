"""The quote email: its text and HTML in both languages, and a failing SMTP server."""

import logging
from datetime import date

import aiosmtplib
import pytest

from novoya_api.quoting.application.dto import QuoteEmail, QuoteTrip
from novoya_api.quoting.infrastructure.email import smtp_quote_notifier
from novoya_api.quoting.infrastructure.email.smtp_quote_notifier import (
    SmtpQuoteNotifier,
    quote_ready_message,
)
from novoya_api.shared.domain.value_objects import Locale
from tests.quoting_fakes import TRIP

URL = "https://novoya.example/quotes/7c0e5b1e-0000-0000-0000-000000000001"
SENDER = "Novoya <no-reply@novoya.example>"


def email(locale: Locale, trip: QuoteTrip = TRIP, name: str | None = "Alice Martin"):
    return QuoteEmail("alice@example.com", name, locale, trip, URL)


def parts(message) -> tuple[str, str]:
    text = message.get_body(("plain",)).get_content()
    html = message.get_body(("html",)).get_content()
    return text, html


@pytest.mark.parametrize(
    ("locale", "subject", "button", "place", "dates"),
    [
        (
            Locale.EN,
            "Your quote is ready",
            "Log in to see my quote",
            "Chania, Greece",
            "May 10, 2026 to May 17, 2026",
        ),
        (
            Locale.FR,
            "Votre devis est prêt",
            "Me connecter pour voir mon devis",
            "Chania, Grèce",
            "du 10 mai 2026 au 17 mai 2026",
        ),
    ],
)
def test_the_email_says_where_the_quote_is(locale, subject, button, place, dates):
    message = quote_ready_message(email(locale), SENDER)
    text, html = parts(message)

    assert message["Subject"] == subject
    assert message["To"] == "alice@example.com"
    assert message["From"] == SENDER
    for body in (text, html):
        assert button in body
        assert place in body
        assert dates in body
        assert "Novoya" in body
    assert f'<a href="{URL}"' in html
    assert URL in text


def test_the_email_holds_no_pdf_and_no_price():
    message = quote_ready_message(email(Locale.EN), SENDER)
    text, html = parts(message)

    assert list(message.iter_attachments()) == []
    for body in (text, html):
        assert "€" not in body
        assert "EUR" not in body
        assert "1234" not in body


def test_the_client_is_greeted_by_name_or_not():
    named, _ = parts(quote_ready_message(email(Locale.FR), SENDER))
    unnamed, _ = parts(quote_ready_message(email(Locale.FR, name=None), SENDER))

    assert named.startswith("Bonjour Alice Martin,")
    assert unnamed.startswith("Bonjour,")


def test_missing_trip_details_are_left_out():
    trip = QuoteTrip(None, None, date(2026, 5, 10), None)
    text, _ = parts(quote_ready_message(email(Locale.EN, trip), SENDER))

    assert "Destination" not in text
    assert "Dates: May 10, 2026\n" in text


def test_names_from_the_catalog_are_escaped_in_the_html():
    trip = QuoteTrip("Greece", "<script>alert(1)</script>", None, None)
    _, html = parts(quote_ready_message(email(Locale.EN, trip), SENDER))

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


async def test_a_sent_email_returns_true(monkeypatch):
    sent = []

    async def fake_send(message, **options):
        sent.append((message, options))

    monkeypatch.setattr(smtp_quote_notifier.aiosmtplib, "send", fake_send)
    notifier = SmtpQuoteNotifier("smtp.example", 587, SENDER, "user", "secret", start_tls=True)

    assert await notifier.send_quote_ready(email(Locale.EN)) is True
    [(message, options)] = sent
    assert message["To"] == "alice@example.com"
    assert options["hostname"] == "smtp.example"
    assert options["port"] == 587
    assert options["start_tls"] is True


async def test_a_failing_server_returns_false_and_logs_no_address(monkeypatch, caplog):
    async def failing_send(message, **options):
        raise aiosmtplib.SMTPRecipientsRefused([])

    monkeypatch.setattr(smtp_quote_notifier.aiosmtplib, "send", failing_send)
    # Alembic's fileConfig, run by the SQL tests, disables the loggers that exist already.
    monkeypatch.setattr(smtp_quote_notifier.logger, "disabled", False)
    notifier = SmtpQuoteNotifier("smtp.example", 587, SENDER)

    with caplog.at_level(logging.ERROR):
        assert await notifier.send_quote_ready(email(Locale.EN)) is False

    assert "SMTPRecipientsRefused" in caplog.text
    assert "alice@example.com" not in caplog.text


async def test_a_message_that_cannot_be_built_returns_false(monkeypatch, caplog):
    def broken_message(email, sender):
        raise KeyError("a template or Babel bug")

    sent = []

    async def fake_send(message, **options):
        sent.append(message)

    monkeypatch.setattr(smtp_quote_notifier, "quote_ready_message", broken_message)
    monkeypatch.setattr(smtp_quote_notifier.aiosmtplib, "send", fake_send)
    monkeypatch.setattr(smtp_quote_notifier.logger, "disabled", False)
    notifier = SmtpQuoteNotifier("smtp.example", 587, SENDER)

    with caplog.at_level(logging.ERROR):
        assert await notifier.send_quote_ready(email(Locale.EN)) is False

    assert sent == []
    assert "KeyError" in caplog.text
