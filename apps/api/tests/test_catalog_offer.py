from datetime import date
from uuid import uuid4

import pytest

from novoya_api.catalog.domain import (
    InvalidOffer,
    InvalidPartner,
    Offer,
    OfferKind,
    Partner,
    PartnerKind,
    PriceUnit,
    normalize_place,
    normalize_tags,
)
from novoya_api.shared.domain.errors import InvalidInput

SEASON_START = date(2026, 4, 1)
SEASON_END = date(2026, 10, 31)


def _partner(**overrides: object) -> Partner:
    values: dict[str, object] = {
        "id": uuid4(),
        "name": "Test partner",
        "kind": PartnerKind.HOTEL,
        "country": "Greece",
        "city": "Chania",
        "contact_email": "p@example.com",
        "contact_phone": "+30 000",
        "active": True,
    }
    values.update(overrides)
    return Partner(**values)  # type: ignore[arg-type]


def _offer(**overrides: object) -> Offer:
    partner_id = overrides.get("partner_id", uuid4())
    values: dict[str, object] = {
        "id": uuid4(),
        "partner_id": partner_id,
        "kind": OfferKind.HOTEL,
        "title": "Test stay",
        "description": "A room",
        "country": "Greece",
        "city": "Chania",
        "min_persons": 2,
        "max_persons": 4,
        "available_from": SEASON_START,
        "available_to": SEASON_END,
        "tags": ("style:beach", "rhythm:calm"),
        "featured": False,
        "active": True,
    }
    values.update(overrides)
    return Offer(**values)  # type: ignore[arg-type]


def test_offer_fits_when_persons_and_dates_are_inside_limits():
    offer = _offer()
    assert offer.fits(persons=2, start=date(2026, 5, 1), end=date(2026, 5, 8)) is True
    assert offer.fits(persons=4, start=SEASON_START, end=SEASON_END) is True


def test_offer_rejects_too_few_persons():
    offer = _offer(min_persons=2, max_persons=4)
    assert offer.fits(persons=1, start=date(2026, 5, 1), end=date(2026, 5, 8)) is False


def test_offer_rejects_too_many_persons():
    offer = _offer(min_persons=2, max_persons=4)
    assert offer.fits(persons=5, start=date(2026, 5, 1), end=date(2026, 5, 8)) is False


def test_offer_rejects_trip_starting_before_availability():
    offer = _offer()
    assert offer.fits(persons=2, start=date(2026, 3, 20), end=date(2026, 5, 8)) is False


def test_offer_rejects_trip_ending_after_availability():
    offer = _offer()
    assert offer.fits(persons=2, start=date(2026, 5, 1), end=date(2026, 11, 2)) is False


def test_offer_rejects_inverted_trip_dates():
    offer = _offer()
    assert offer.fits(persons=2, start=date(2026, 5, 8), end=date(2026, 5, 1)) is False


def test_invalid_person_limits_are_rejected():
    with pytest.raises(InvalidOffer):
        _offer(min_persons=4, max_persons=2)


def test_min_persons_below_one_is_rejected():
    with pytest.raises(InvalidOffer):
        _offer(min_persons=0, max_persons=2)


def test_invalid_availability_dates_are_rejected():
    with pytest.raises(InvalidOffer):
        _offer(available_from=SEASON_END, available_to=SEASON_START)


def test_inactive_partner_hides_offers():
    partner = _partner(active=False)
    offer = _offer(partner_id=partner.id, active=True)
    assert offer.is_listed_with(partner) is False


def test_inactive_offer_is_not_listed():
    partner = _partner(active=True)
    offer = _offer(partner_id=partner.id, active=False)
    assert offer.is_listed_with(partner) is False
    assert offer.fits(persons=2, start=date(2026, 5, 1), end=date(2026, 5, 8)) is True


def test_a_hidden_offer_is_not_listed():
    partner = _partner()
    offer = _offer(partner_id=partner.id, hidden=True)
    assert offer.is_listed_with(partner) is False


def test_a_hidden_partner_hides_its_offers():
    partner = _partner(hidden=True)
    offer = _offer(partner_id=partner.id)
    assert offer.is_listed_with(partner) is False


def test_offers_and_partners_are_shown_and_hand_made_by_default():
    partner = _partner()
    assert (partner.hidden, partner.imported, _offer().hidden) == (False, False, False)


def test_is_listed_with_rejects_another_partner():
    partner = _partner()
    other = _partner()
    offer = _offer(partner_id=partner.id)
    with pytest.raises(InvalidOffer):
        offer.is_listed_with(other)


def test_invalid_offer_is_a_422_input_error():
    assert issubclass(InvalidOffer, InvalidInput)


def test_offer_rejects_a_tag_that_is_not_section_tag():
    with pytest.raises(InvalidOffer):
        _offer(tags=("beach",))


def test_normalize_tags_lowercases_and_drops_duplicates():
    assert normalize_tags([" STYLE:Beach ", "style:beach", "food:local"]) == (
        "style:beach",
        "food:local",
    )


def test_normalize_place_title_cases_english_names():
    assert normalize_place("  greece ") == "Greece"
    assert normalize_place("CHANIA") == "Chania"


@pytest.mark.parametrize("tag", ["style:café", "food:fish&chips", "a:b:c", "style:", ":beach"])
def test_normalize_tags_refuses_ids_the_panel_cannot_use(tag):
    with pytest.raises(InvalidOffer):
        normalize_tags([tag])


def test_normalize_tags_keeps_slug_ids():
    assert normalize_tags(["Style:Sea_View", "food:street-food"]) == (
        "style:sea_view",
        "food:street-food",
    )


def test_normalize_place_capitalises_after_hyphens_and_apostrophes():
    assert normalize_place("saint-tropez") == "Saint-Tropez"
    assert normalize_place("l'isle-sur-la-sorgue") == "L'Isle-Sur-La-Sorgue"


def test_empty_partner_name_is_rejected():
    with pytest.raises(InvalidPartner):
        _partner(name="  ")


def test_offer_has_no_price_unless_one_is_given():
    offer = _offer()

    assert offer.price_eur is None
    assert offer.price_unit is None
    assert offer.opening_months == ()


def test_offer_keeps_a_price_with_its_unit():
    offer = _offer(price_eur=85, price_unit=PriceUnit("person/night"), opening_months=(5, 6))

    assert offer.price_eur == 85
    assert offer.price_unit == "person/night"
    assert offer.opening_months == (5, 6)


@pytest.mark.parametrize(
    ("price", "unit"),
    [(85, None), (None, PriceUnit("person/trip"))],
    ids=["price without unit", "unit without price"],
)
def test_offer_price_and_unit_come_together(price, unit):
    with pytest.raises(InvalidOffer):
        _offer(price_eur=price, price_unit=unit)


@pytest.mark.parametrize("price", [0, -5])
def test_offer_price_must_be_more_than_zero(price):
    with pytest.raises(InvalidOffer):
        _offer(price_eur=price, price_unit=PriceUnit("person/activity"))


def test_price_units_are_per_person():
    assert {unit.value for unit in PriceUnit} == {
        "person/night",
        "person/trip",
        "person/activity",
    }


@pytest.mark.parametrize("months", [(0,), (13,), (5, 13)])
def test_opening_months_must_be_1_to_12(months):
    with pytest.raises(InvalidOffer):
        _offer(opening_months=months)


def test_partner_without_a_phone_is_valid():
    assert _partner(contact_phone=None).contact_phone is None


def test_blank_partner_phone_becomes_none():
    assert _partner(contact_phone="   ").contact_phone is None


def test_offer_without_opening_months_fits_any_month_of_its_season():
    offer = _offer(opening_months=())

    assert offer.fits(persons=2, start=date(2026, 4, 1), end=date(2026, 10, 31)) is True


def test_offer_fits_a_trip_inside_its_opening_months():
    offer = _offer(opening_months=(5, 6))

    assert offer.fits(persons=2, start=date(2026, 5, 25), end=date(2026, 6, 3)) is True


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 7, 1), date(2026, 7, 8)),
        (date(2026, 6, 28), date(2026, 7, 2)),
        (date(2026, 4, 30), date(2026, 5, 3)),
    ],
    ids=["closed month", "ends in a closed month", "starts in a closed month"],
)
def test_offer_does_not_fit_a_trip_that_touches_a_closed_month(start, end):
    offer = _offer(opening_months=(5, 6))

    assert offer.fits(persons=2, start=start, end=end) is False


def test_a_trip_over_a_new_year_needs_both_months_open():
    offer = _offer(
        available_from=date(2026, 1, 1), available_to=date(2027, 12, 31), opening_months=(12,)
    )

    assert offer.fits(persons=2, start=date(2026, 12, 28), end=date(2027, 1, 3)) is False
    assert offer.fits(persons=2, start=date(2026, 12, 20), end=date(2026, 12, 27)) is True
