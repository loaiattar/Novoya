"""The email that confirms the agency received the trip (#168): EN and FR, the answer time from
the setting, a link to the plan, and a failure logged without the address."""

import logging

import aiosmtplib
import pytest
from pydantic import ValidationError

from novoya_api.config import Settings
from novoya_api.planning.application.dto import RequestReceivedEmail
from novoya_api.planning.infrastructure.email import smtp_request_notifier
from novoya_api.planning.infrastructure.email.smtp_request_notifier import (
    SmtpRequestNotifier,
    request_received_message,
)
from novoya_api.shared.domain.value_objects import Locale

SENDER = "Novoya <no-reply@novoya.test>"
URL = "https://novoya.test/plans/00000000-0000-0000-0000-000000000001"


def email(locale: Locale, name: str | None = "Camille", days: int = 4) -> RequestReceivedEmail:
    return RequestReceivedEmail("camille@example.fr", name, locale, URL, days)


@pytest.mark.parametrize(
    ("locale", "subject", "promise"),
    [
        (Locale.EN, "The agency received your trip", "within 4 days"),
        (Locale.FR, "L'agence a bien reçu votre voyage", "sous 4 jours"),
    ],
)
def test_the_email_confirms_in_the_client_language(locale, subject, promise):
    message = request_received_message(email(locale), SENDER)

    assert message["Subject"] == subject
    assert message["To"] == "camille@example.fr"
    assert message["From"] == SENDER
    body = message.get_content()
    assert promise in body
    assert URL in body


def test_the_answer_time_comes_from_the_setting():
    body = request_received_message(email(Locale.EN, days=6), SENDER).get_content()

    assert "within 6 days" in body
    assert "4 days" not in body


def test_the_client_is_greeted_by_name_or_not():
    assert "Hello Camille," in request_received_message(email(Locale.EN), SENDER).get_content()
    body = request_received_message(email(Locale.FR, None), SENDER).get_content()
    assert body.startswith("Bonjour,")


async def test_a_sent_email_returns_true(monkeypatch):
    sent = []

    async def fake_send(message, **options):
        sent.append((message, options))

    monkeypatch.setattr(smtp_request_notifier.aiosmtplib, "send", fake_send)
    notifier = SmtpRequestNotifier("smtp.example", 587, SENDER, start_tls=True)

    assert await notifier.send_request_received(email(Locale.EN)) is True
    assert sent[0][1]["hostname"] == "smtp.example"
    assert sent[0][1]["start_tls"] is True


async def test_a_failing_server_returns_false_and_logs_no_address(monkeypatch, caplog):
    async def failing_send(message, **options):
        raise aiosmtplib.SMTPRecipientsRefused([])

    monkeypatch.setattr(smtp_request_notifier.aiosmtplib, "send", failing_send)
    # Alembic's fileConfig, run by the SQL tests, disables the loggers that exist already.
    monkeypatch.setattr(smtp_request_notifier.logger, "disabled", False)
    notifier = SmtpRequestNotifier("smtp.example", 587, SENDER)

    with caplog.at_level(logging.ERROR):
        assert await notifier.send_request_received(email(Locale.EN)) is False

    assert "SMTPRecipientsRefused" in caplog.text
    assert "camille@example.fr" not in caplog.text


@pytest.mark.parametrize(
    ("locale", "promise"),
    [(Locale.EN, "within 1 day."), (Locale.FR, "sous 1 jour.")],
)
def test_one_day_is_singular(locale, promise):
    body = request_received_message(email(locale, days=1), SENDER).get_content()

    assert promise in body
    assert "1 days" not in body
    assert "1 jours" not in body


@pytest.mark.parametrize("days", [0, -1, 31])
def test_the_answer_time_setting_refuses_a_value_out_of_bounds(days):
    with pytest.raises(ValidationError):
        Settings(quote_answer_days=days)


@pytest.mark.parametrize("days", [1, 4, 30])
def test_the_answer_time_setting_takes_1_to_30_days(days):
    assert Settings(quote_answer_days=days).quote_answer_days == days
