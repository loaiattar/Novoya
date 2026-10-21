from datetime import date
from uuid import uuid4

import pytest

from novoya_api.catalog.domain import Extra, ExtraPricing, InvalidExtra, InvalidReview, Review
from novoya_api.shared.domain.errors import InvalidInput


def _review(**overrides: object) -> Review:
    values: dict[str, object] = {
        "id": uuid4(),
        "country": "Greece",
        "city": "Chania",
        "rating": 5,
        "reviewed_on": date(2026, 6, 1),
        "text": "A made-up stay by the sea.",
        "author": "Zélie Q.",
    }
    values.update(overrides)
    return Review(**values)  # type: ignore[arg-type]


def _extra(**overrides: object) -> Extra:
    values: dict[str, object] = {
        "id": uuid4(),
        "category": "transport",
        "label": "Extra bag",
        "description": "One more bag in the hold",
        "pricing": ExtraPricing("supplement"),
        "supplement_eur": 25,
        "unit": "par bagage",
        "constraints": ("Ask before the trip",),
        "active": True,
    }
    values.update(overrides)
    return Extra(**values)  # type: ignore[arg-type]


def test_review_and_extra_errors_are_422_input_errors():
    assert issubclass(InvalidReview, InvalidInput)
    assert issubclass(InvalidExtra, InvalidInput)


# Review


@pytest.mark.parametrize("rating", [1, 5])
def test_review_rating_from_1_to_5_is_valid(rating):
    assert _review(rating=rating).rating == rating


@pytest.mark.parametrize("rating", [0, 6])
def test_review_rating_outside_1_to_5_is_rejected(rating):
    with pytest.raises(InvalidReview):
        _review(rating=rating)


def test_review_keeps_the_author_as_given():
    assert _review(author="Voyageur anonyme").author == "Voyageur anonyme"


@pytest.mark.parametrize("field", ["author", "text"])
def test_review_with_an_empty_author_or_text_is_rejected(field):
    with pytest.raises(InvalidReview):
        _review(**{field: "  "})


# Extra


def test_extra_pricing_values():
    assert {pricing.value for pricing in ExtraPricing} == {"included", "supplement", "on_quote"}


def test_supplement_extra_keeps_its_amount():
    assert _extra().supplement_eur == 25


@pytest.mark.parametrize("amount", [None, 0, -10])
def test_supplement_extra_needs_an_amount_above_zero(amount):
    with pytest.raises(InvalidExtra):
        _extra(supplement_eur=amount)


@pytest.mark.parametrize("pricing", ["included", "on_quote"])
def test_included_or_on_quote_extra_has_no_amount(pricing):
    assert _extra(pricing=ExtraPricing(pricing), supplement_eur=None).supplement_eur is None
    with pytest.raises(InvalidExtra):
        _extra(pricing=ExtraPricing(pricing), supplement_eur=25)


def test_extra_with_an_empty_label_is_rejected():
    with pytest.raises(InvalidExtra):
        _extra(label=" ")
