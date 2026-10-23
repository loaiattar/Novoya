"""The quote PDF: the Jinja2 HTML in English and French, and the WeasyPrint bytes."""

from dataclasses import fields, replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from babel.dates import format_date

from novoya_api.quoting.application.dto import QuotedItem
from novoya_api.quoting.infrastructure.pdf.renderer import WeasyPrintRenderer
from novoya_api.shared.domain.value_objects import Locale
from tests.quoting_fakes import document


def html_of(locale: Locale) -> str:
    """The HTML with every kind of space as a plain one: Babel's French groups use U+202F."""
    html = WeasyPrintRenderer().html(document(locale))
    return html.replace(" ", " ").replace("\xa0", " ").replace("&nbsp;", " ")


@pytest.fixture(scope="module")
def english() -> str:
    return html_of(Locale.EN)


@pytest.fixture(scope="module")
def french() -> str:
    return html_of(Locale.FR)


def test_the_english_quote_has_an_english_heading(english):
    assert "Quote" in english


def test_the_french_quote_has_a_french_heading(french):
    assert "Devis" in french


def test_the_quote_shows_its_number():
    doc = document(Locale.EN)

    assert doc.quote.number in WeasyPrintRenderer().html(doc)


def test_the_english_total_is_formatted_in_euros(english):
    assert "€1,234.50" in english


def test_the_french_total_is_formatted_in_euros(french):
    assert "1 234,50 €" in french


def test_the_english_quote_shows_the_budget(english):
    assert "€1,500.00" in english


def test_the_french_quote_shows_the_budget(french):
    assert "1 500,00 €" in french


def test_the_quote_shows_each_item_with_its_price(english):
    assert "Sea view room" in english
    assert "Boat trip" in english
    assert "€900.00" in english
    assert "€289.50" in english


def test_the_quote_shows_the_extras(english):
    assert "Private guide" in english
    assert "€45.00" in english
    assert "Breakfast" in english


def test_the_quote_shows_the_wish_and_its_tags(english):
    assert "A quiet week in Chania with seafood" in english
    assert "beach" in english
    assert "seafood" in english


def test_the_quote_shows_the_client_and_the_destination(english):
    assert "Alice Martin" in english
    assert "Chania" in english
    assert "Greece" in english


def test_the_quote_shows_the_agents_contact(english):
    assert "agent@novoya.example" in english


def test_the_english_quote_shows_the_valid_until_date():
    doc = document(Locale.EN)

    html = WeasyPrintRenderer().html(doc)

    assert format_date(doc.quote.valid_until.date(), format="long", locale="en") in html


def test_the_french_quote_shows_the_valid_until_date():
    doc = document(Locale.FR)

    html = WeasyPrintRenderer().html(doc)

    assert format_date(doc.quote.valid_until.date(), format="long", locale="fr") in html


def test_the_english_quote_says_flights_are_not_included(english):
    assert "flights" in english.lower()


def test_the_french_quote_says_flights_are_not_included(french):
    assert "vols" in french.lower()


def test_the_quote_links_to_the_answer_page():
    doc = document(Locale.FR)

    assert doc.answer_url in WeasyPrintRenderer().html(doc)


def test_the_english_quote_has_no_agency_fee_line(english):
    assert "agency fee" not in english.lower()


def test_the_french_quote_has_no_agency_fee_line(french):
    assert "frais d'agence" not in french.lower()
    assert "frais d&#39;agence" not in french.lower()


def test_a_quoted_item_has_no_partner():
    assert not any("partner" in field.name for field in fields(QuotedItem))


@pytest.mark.parametrize("locale", [Locale.EN, Locale.FR])
def test_render_returns_a_pdf(locale):
    pdf = WeasyPrintRenderer().render(document(locale))

    assert pdf.startswith(b"%PDF")


def test_the_pdf_dates_are_paris_dates():
    doc = document(Locale.FR)
    doc.quote.sent_at = datetime(2026, 10, 22, 22, 30, tzinfo=UTC)  # the 23rd in Paris

    assert "23 octobre 2026" in WeasyPrintRenderer().html(doc)


def test_html_in_the_wish_is_shown_as_text():
    doc = document(Locale.EN)
    doc = replace(doc, plan=replace(doc.plan, wish_text='<img src="file:///etc/passwd">'))

    html = WeasyPrintRenderer().html(doc)

    assert '<img src="file' not in html
    assert "&lt;img" in html


@pytest.mark.parametrize("locale", [Locale.EN, Locale.FR])
def test_the_quote_comes_from_the_agency(locale):
    html = WeasyPrintRenderer().html(document(locale))

    assert "DÉTOUR Voyages" in html
    assert "contact@detour-voyages.fr" in html
    assert "compte Novoya" not in html and "Novoya account" not in html


def test_the_pdf_never_fetches_a_file(tmp_path, monkeypatch):
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"not an image")
    renderer = WeasyPrintRenderer()
    page = renderer.html(document(Locale.EN))
    monkeypatch.setattr(
        renderer, "html", lambda doc: page.replace("</body>", f'<img src="file://{secret}">')
    )
    opened = []
    real_open = open

    def spy(path, *args, **kwargs):
        opened.append(str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", spy)

    assert renderer.render(document(Locale.EN)).startswith(b"%PDF")
    assert str(secret) not in opened


@pytest.mark.parametrize("locale", [Locale.EN, Locale.FR])
def test_the_quote_gives_the_agencys_phone_number(locale):
    assert "+33 2 40 00 00 00" in html_of(locale)


def pages_of(doc) -> int:
    from weasyprint import HTML

    return len(HTML(string=WeasyPrintRenderer().html(doc)).render().pages)


@pytest.mark.parametrize("locale", [Locale.EN, Locale.FR])
def test_a_three_item_trip_fits_on_one_page(locale):
    doc = document(locale)
    items = tuple(
        QuotedItem(day, "hotel", f"Item {day}", "A short description", 2, Decimal("100"))
        for day in (1, 2, 3)
    )

    assert pages_of(replace(doc, plan=replace(doc.plan, items=items))) == 1


def test_the_price_column_says_it_is_the_line_amount(english, french):
    assert "Amount" in english
    assert "Montant" in french


def test_the_french_quote_names_the_country_in_french(french):
    assert "Chania, Grèce" in french


def test_the_english_quote_names_the_country_in_english(english):
    assert "Chania, Greece" in english


def test_an_unknown_country_is_shown_as_stored():
    doc = document(Locale.FR)
    doc = replace(doc, plan=replace(doc.plan, country="Atlantis"))

    assert "Chania, Atlantis" in WeasyPrintRenderer().html(doc)
