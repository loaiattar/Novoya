"""DÉTOUR import, read and mapped from a made-up sqlite file: no PostgreSQL needed."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from novoya_api.catalog.application.use_cases.search_offers import SearchOffers
from novoya_api.catalog.domain import ExtraPricing, OfferKind, PartnerKind, normalize_tags
from novoya_api.catalog.infrastructure.countries import COUNTRIES, canonical_country
from novoya_api.catalog.infrastructure.detour.__main__ import main
from novoya_api.catalog.infrastructure.detour.mapping import (
    DetourCatalog,
    DetourImportError,
    detour_id,
    slugify,
)
from novoya_api.catalog.infrastructure.detour.read import open_source, read_catalog
from tests.detour_fixture import (
    CHANIA,
    CHANIA_STAY,
    CHANIA_TRANSFER,
    LUZ_MUSEUM,
    SECRET_PARTNER_EMAIL,
    SECRET_PARTNER_NAME,
    DetourFile,
    sample_detour,
)


@pytest.fixture
def source(tmp_path) -> Path:
    return sample_detour(tmp_path / "detour.sqlite")


@pytest.fixture
def catalog(source) -> DetourCatalog:
    return read_catalog(source)


def partner(catalog: DetourCatalog, source_id: str):
    return {item.id: item for item in catalog.partners}[detour_id("partenaires", source_id)]


def offer(catalog: DetourCatalog, source_id: str):
    return {item.id: item for item in catalog.offers}[detour_id("offres", source_id)]


def extra(catalog: DetourCatalog, source_id: str):
    return {item.id: item for item in catalog.extras}[detour_id("preferences", source_id)]


def import_error(path: Path) -> str:
    with pytest.raises(DetourImportError) as raised:
        read_catalog(path)
    return str(raised.value)


# Partners


@pytest.mark.parametrize(
    ("source_type", "kind"),
    [
        ("hebergement", PartnerKind.HOTEL),
        ("transport", PartnerKind.TRANSPORT),
        ("activite", PartnerKind.ACTIVITY),
    ],
)
def test_partner_kind_follows_the_detour_type(tmp_path, source_type, kind):
    path = tmp_path / "detour.sqlite"
    with DetourFile(path) as detour:
        detour.destination(CHANIA, "Chania", "Grèce")
        detour.partner("P001", CHANIA, type=source_type)

    imported = read_catalog(path)

    assert partner(imported, "P001").kind is kind


def test_unknown_partner_type_is_an_error_that_names_the_id_only(tmp_path):
    path = tmp_path / "detour.sqlite"
    with DetourFile(path) as detour:
        detour.destination(CHANIA, "Chania", "Grèce")
        detour.partner(
            "P009",
            CHANIA,
            nom=SECRET_PARTNER_NAME,
            type="croisiere",
            contact_email=SECRET_PARTNER_EMAIL,
        )

    message = import_error(path)

    assert "P009" in message
    assert SECRET_PARTNER_NAME not in message
    assert SECRET_PARTNER_EMAIL not in message


def test_partner_place_comes_from_its_destination(catalog):
    stay = partner(catalog, "P001")

    assert (stay.country, stay.city) == ("Greece", "Chania")


def test_city_is_kept_as_given_with_whitespace_collapsed(catalog):
    workshop = partner(catalog, "P003")

    assert (workshop.country, workshop.city) == ("France", "Saint-Jean de Luz")


def test_unmapped_country_is_rejected_with_the_destination_id(tmp_path):
    path = tmp_path / "detour.sqlite"
    with DetourFile(path) as detour:
        detour.destination("D777", "Ville inventée", "Atlantide")
        detour.partner("P001", "D777")

    message = import_error(path)

    assert "D777" in message


def test_partner_has_no_phone_and_keeps_name_and_email(catalog):
    stay = partner(catalog, "P001")

    assert stay.contact_phone is None
    assert stay.name == SECRET_PARTNER_NAME
    assert stay.contact_email == SECRET_PARTNER_EMAIL


def test_partner_is_active_only_when_its_status_is_actif(catalog):
    assert partner(catalog, "P001").active is True
    assert partner(catalog, "P003").active is False


# Countries


@pytest.mark.parametrize(
    ("french", "english"),
    [("Grèce", "Greece"), ("Corée du Sud", "South Korea"), ("Côte d’Ivoire", "Ivory Coast")],
)
def test_detour_country_names_are_translated_to_english(french, english):
    assert canonical_country(french) == english


@pytest.mark.parametrize(
    ("name", "english"),
    [
        # Not in the DÉTOUR map: a country the client adds later, in French or in English.
        ("Allemagne", "Germany"),
        ("Brésil", "Brazil"),
        ("Jordanie", "Jordan"),
        ("Nouvelle-Calédonie", "New Caledonia"),
        ("Germany", "Germany"),
        ("Uruguay", "Uruguay"),
    ],
)
def test_a_new_country_in_french_or_english_gets_its_english_name(name, english):
    assert canonical_country(name) == english


def test_the_detour_map_wins_over_the_standard_names():
    # The standard English name is "Côte d’Ivoire"; rows already imported say "Ivory Coast".
    assert canonical_country("Côte d’Ivoire") == "Ivory Coast"
    assert canonical_country("Ivory Coast") == "Ivory Coast"


@pytest.mark.parametrize("name", ["Atlantide", "Europe", "Monde", "", "ZZ"])
def test_an_unknown_country_has_no_english_name(name):
    assert canonical_country(name) is None


def test_the_country_map_covers_the_86_detour_countries():
    assert len(COUNTRIES) == 86


# Offers


def test_offer_takes_title_description_place_and_partner(catalog):
    stay = offer(catalog, CHANIA_STAY)

    assert stay.title == "Chania - nuit en chambre double"
    assert stay.description == "Une chambre double près du port"
    assert stay.kind is OfferKind.HOTEL
    assert (stay.country, stay.city) == ("Greece", "Chania")
    assert stay.partner_id == detour_id("partenaires", "P001")


def test_offer_persons_go_from_one_to_its_capacity(catalog):
    transfer = offer(catalog, CHANIA_TRANSFER)

    assert (transfer.min_persons, transfer.max_persons) == (1, 8)


def test_offer_with_zero_capacity_is_rejected_with_its_id(source):
    with DetourFile(source) as detour:
        detour.offer("F099", "P001", CHANIA, nom="Offre secrète", capacite=0)

    message = import_error(source)

    assert "F099" in message
    assert "Offre secrète" not in message


def test_offer_availability_is_its_validity(catalog):
    stay = offer(catalog, CHANIA_STAY)

    assert (stay.available_from, stay.available_to) == (date(2026, 11, 1), date(2027, 10, 31))


@pytest.mark.parametrize(
    ("source_id", "price", "unit"),
    [
        (CHANIA_STAY, 85, "person/night"),
        (CHANIA_TRANSFER, 30, "person/trip"),
        (LUZ_MUSEUM, 15, "person/activity"),
    ],
)
def test_offer_price_and_unit_are_mapped(catalog, source_id, price, unit):
    mapped = offer(catalog, source_id)

    assert mapped.price_eur == price
    assert mapped.price_unit == unit


def test_unknown_price_unit_is_rejected_with_the_offer_id(source):
    with DetourFile(source) as detour:
        detour.offer("F098", "P001", CHANIA, unite="personne/semaine")

    assert "F098" in import_error(source)


def test_opening_months_are_sorted_without_repeats(catalog):
    assert offer(catalog, CHANIA_STAY).opening_months == (5, 6, 9)


def test_month_13_is_rejected_with_the_offer_id(source):
    with DetourFile(source) as detour:
        detour.offer("F097", "P001", CHANIA, months=(12, 13))

    assert "F097" in import_error(source)


def test_offer_terms_are_copied(catalog):
    stay = offer(catalog, CHANIA_STAY)

    assert stay.conditions == "Petit-déjeuner inclus"
    assert stay.restrictions == "Non-fumeur"
    assert stay.cancellation == "Gratuite jusqu'à 7 jours avant"
    assert stay.confirmation_delay_hours == 24


def test_offer_without_terms_keeps_them_empty(catalog):
    transfer = offer(catalog, CHANIA_TRANSFER)

    assert transfer.conditions is None
    assert transfer.restrictions is None
    assert transfer.cancellation is None
    assert transfer.confirmation_delay_hours is None


def test_hotel_offer_is_tagged_as_a_stay(catalog):
    assert "accommodation:stay" in offer(catalog, CHANIA_STAY).tags


def test_transport_offer_is_tagged_as_a_transfer(catalog):
    assert "transport:transfer" in offer(catalog, CHANIA_TRANSFER).tags


def test_activity_offer_is_tagged_with_its_title_and_the_destination_strengths(catalog):
    tags = offer(catalog, LUZ_MUSEUM).tags

    assert {"activities:musee-national", "style:surf-ocean"} <= set(tags)


def test_every_imported_tag_is_a_catalog_tag(catalog):
    for mapped in catalog.offers:
        assert normalize_tags(mapped.tags) == mapped.tags
        assert all(tag.isascii() for tag in mapped.tags)


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("Musée national", "musee-national"),
        ("  Surf & océan ", "surf-ocean"),
        ("L’Atelier, du port", "l-atelier-du-port"),
        ("Balade à vélo", "balade-a-velo"),
        ("—", ""),
    ],
)
def test_slugify_gives_ascii_ids(text, slug):
    assert slugify(text) == slug


# Ids


def test_ids_are_stable_from_one_run_to_the_next(source, catalog):
    again = read_catalog(source)

    assert {item.id for item in again.partners} == {item.id for item in catalog.partners}
    assert {item.id for item in again.offers} == {item.id for item in catalog.offers}
    assert detour_id("offres", "F001") == detour_id("offres", "F001")


def test_ids_differ_from_one_detour_table_to_another():
    assert detour_id("partenaires", "X001") != detour_id("offres", "X001")
    assert detour_id("avis", "X001") != detour_id("preferences", "X001")


# Reviews


def test_reviews_come_only_from_the_publishable_view(catalog):
    assert {review.id for review in catalog.reviews} == {
        detour_id("avis", "A001"),
        detour_id("avis", "A002"),
        detour_id("avis", "A004"),
    }
    assert "Ancienne table." not in {review.text for review in catalog.reviews}


def test_review_author_is_kept_as_given(catalog):
    authors = {review.id: review.author for review in catalog.reviews}

    assert authors[detour_id("avis", "A001")] == "Zélie Q."
    assert authors[detour_id("avis", "A002")] == "Voyageur anonyme"


def test_review_carries_the_destination_of_its_circuit(catalog):
    review = {review.id: review for review in catalog.reviews}[detour_id("avis", "A002")]

    assert (review.country, review.city) == ("France", "Saint-Jean de Luz")
    assert review.rating == 4
    assert review.reviewed_on == date(2026, 7, 15)
    assert review.text == "Très bon accueil, inventé aussi."


# Extras


@pytest.mark.parametrize(
    ("source_id", "pricing", "supplement"),
    [
        ("O001", ExtraPricing("included"), None),
        ("O002", ExtraPricing("supplement"), 25),
        ("O003", ExtraPricing("on_quote"), None),
    ],
)
def test_extra_pricing_is_mapped(catalog, source_id, pricing, supplement):
    mapped = extra(catalog, source_id)

    assert mapped.pricing is pricing
    assert mapped.supplement_eur == supplement


def test_extra_keeps_its_label_category_and_unit(catalog):
    bag = extra(catalog, "O002")

    assert (bag.category, bag.label, bag.unit) == ("transport", "Bagage en plus", "par bagage")
    assert bag.description == "Un bagage en soute de plus"
    assert bag.active is True


def test_supplement_without_an_amount_is_rejected_with_its_id(source):
    with DetourFile(source) as detour:
        detour.preference("O099", tarification="supplement", supplement_eur=None)

    assert "O099" in import_error(source)


def test_unknown_extra_pricing_is_rejected_with_its_id(source):
    with DetourFile(source) as detour:
        detour.preference("O098", tarification="gratuit")

    assert "O098" in import_error(source)


def test_extra_constraints_keep_their_position_order(catalog):
    assert extra(catalog, "O001").constraints == ("Selon disponibilité", "Demande à l'avance")
    assert extra(catalog, "O002").constraints == ()


# Source file


def test_source_is_opened_read_only(source):
    connection = open_source(source)
    try:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM partenaires")
    finally:
        connection.close()


def test_missing_source_file_exits_with_a_message(tmp_path, capsys):
    missing = tmp_path / "absent.sqlite"

    assert main(["--source", str(missing)]) == 1
    assert str(missing) in capsys.readouterr().err
    assert not missing.exists()


def test_sample_imports_every_partner_offer_and_extra(catalog):
    assert len(catalog.partners) == 3
    assert len(catalog.offers) == 3
    assert len(catalog.extras) == 3


# Style tags on every offer, so a style-only wish still finds a bed and a transfer


def test_hotel_and_transfer_offers_carry_the_destination_styles(catalog):
    assert {"accommodation:stay", "style:plages-secretes", "style:cuisine-cretoise"} <= set(
        offer(catalog, CHANIA_STAY).tags
    )
    assert {"transport:transfer", "style:plages-secretes"} <= set(
        offer(catalog, CHANIA_TRANSFER).tags
    )


class CatalogOffers:
    """An OfferRepository over the imported entities, enough for SearchOffers."""

    def __init__(self, imported: DetourCatalog) -> None:
        self.partners = {item.id: item for item in imported.partners}
        self.offers = imported.offers

    async def list_at(self, country: str, city: str | None):
        return [
            (item, self.partners[item.partner_id])
            for item in self.offers
            if item.country.lower() == country.lower()
            and (city is None or item.city.lower() == city.lower())
        ]


async def test_a_style_only_search_finds_the_hotel_and_the_transfer(tmp_path):
    path = tmp_path / "detour.sqlite"
    with DetourFile(path) as detour:
        detour.destination(CHANIA, "Chania", "Grèce", ("Plages secrètes",))
        detour.partner("P001", CHANIA, type="hebergement")
        detour.partner("P002", CHANIA, type="transport")
        detour.offer("F001", "P001", CHANIA, type="hebergement", capacite=4)
        detour.offer("F002", "P002", CHANIA, type="transport", unite="personne/trajet", capacite=8)
    search = SearchOffers(CatalogOffers(read_catalog(path)))

    found = await search(
        "Greece", "Chania", ["style:plages-secretes"], 2, date(2027, 5, 1), date(2027, 5, 8)
    )

    assert {view.id for view in found} == {detour_id("offres", "F001"), detour_id("offres", "F002")}
