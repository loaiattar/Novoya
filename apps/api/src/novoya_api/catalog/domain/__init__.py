"""Domain: Partner, Offer (tags, person limits, availability, featured, active, hidden, an
indicative price), Review (published, pseudonymised), Extra (an option on a plan). Pure Python.

Rules: inactive or hidden partners hide their offers; an offer fits a group size and dates or
not. DÉTOUR owns the content of imported rows; Novoya owns featured and hidden.
"""

from novoya_api.catalog.domain.errors import (
    ExtraNotFound,
    ImportedRow,
    InvalidPartner,
    OfferNotFound,
    PartnerNotFound,
)
from novoya_api.catalog.domain.extra import Extra, ExtraPricing, InvalidExtra
from novoya_api.catalog.domain.kinds import OfferKind, PartnerKind
from novoya_api.catalog.domain.offer import InvalidOffer, Offer, PriceUnit, normalize_tags
from novoya_api.catalog.domain.partner import Partner, normalize_place
from novoya_api.catalog.domain.review import InvalidReview, Review

__all__ = [
    "Extra",
    "ExtraNotFound",
    "ExtraPricing",
    "ImportedRow",
    "InvalidExtra",
    "InvalidOffer",
    "InvalidPartner",
    "InvalidReview",
    "Offer",
    "OfferKind",
    "OfferNotFound",
    "Partner",
    "PartnerKind",
    "PartnerNotFound",
    "PriceUnit",
    "Review",
    "normalize_place",
    "normalize_tags",
]
