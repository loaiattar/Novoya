"""Dates and countries in the quote's language, for the PDF and the email."""

from datetime import date, datetime
from functools import cache

from babel import Locale as BabelLocale
from babel.dates import format_date

from novoya_api.quoting.domain.quote import AGENCY_TIMEZONE
from novoya_api.shared.domain.value_objects import Locale


def day(value: date | datetime, locale: Locale) -> str:
    plain = value.astimezone(AGENCY_TIMEZONE).date() if isinstance(value, datetime) else value
    return format_date(plain, format="long", locale=locale.value)


@cache
def _territory_codes() -> dict[str, str]:
    """English country name -> CLDR code. Novoya stores countries by their English name."""
    return {name: code for code, name in BabelLocale("en").territories.items()}


def country(name: str | None, locale: Locale) -> str | None:
    """The country in the quote's language: "Greece" -> "Grèce". An unknown name as stored."""
    code = _territory_codes().get(name) if name else None
    if code is None:
        return name
    return BabelLocale(locale.value).territories.get(code, name)
