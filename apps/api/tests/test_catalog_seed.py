from datetime import date, timedelta

import pytest

from novoya_api.catalog.domain.kinds import OfferKind, PartnerKind
from novoya_api.catalog.infrastructure.seed.data import OFFERS, PARTNERS
from novoya_api.catalog.infrastructure.seed.run import seed_catalog
from novoya_api.config import get_settings

ALLOWED_SECTIONS = {"style", "rhythm", "accommodation", "activities", "food", "transport"}


def test_seed_covers_at_least_three_destinations():
    destinations = {(row["country"], row["city"]) for row in PARTNERS}
    assert len(destinations) >= 3


def test_seed_has_an_offer_of_every_kind():
    kinds = {row["kind"] for row in OFFERS}
    assert kinds == set(OfferKind)


def test_seed_offers_all_have_tags():
    assert all(row["tags"] for row in OFFERS)


def test_seed_tags_use_allowed_sections():
    for row in OFFERS:
        for tag in row["tags"]:
            assert ":" in tag, tag
            section, name = tag.split(":", 1)
            assert section in ALLOWED_SECTIONS, tag
            assert name, tag


def test_seed_places_are_english_title_case():
    for row in [*PARTNERS, *OFFERS]:
        assert row["country"] == row["country"].title()
        assert row["city"] == row["city"].title()
        assert row["country"].isascii()
        assert row["city"].isascii()


def test_seed_partners_have_contact_phone():
    assert all(row["contact_phone"] for row in PARTNERS)


def test_seed_has_every_partner_kind():
    kinds = {row["kind"] for row in PARTNERS}
    assert kinds == set(PartnerKind)


def test_seed_season_never_expires_for_a_trip_in_the_coming_year():
    """Computed when the seed runs, so a developer can always plan a trip from today."""
    today = date.today()
    for row in OFFERS:
        assert row["available_from"] <= today
        assert row["available_to"] >= today + timedelta(days=365)


def test_seed_offers_have_no_price_field():
    for row in OFFERS:
        assert "price" not in row
        assert "negotiated_price" not in row


async def test_seed_refuses_non_development(monkeypatch):
    monkeypatch.setenv("NOVOYA_ENV", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="development"):
            await seed_catalog()
    finally:
        get_settings.cache_clear()
