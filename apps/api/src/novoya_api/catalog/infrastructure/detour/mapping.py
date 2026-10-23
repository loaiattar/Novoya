"""DÉTOUR rows to catalog entities. Pure: read.py does the SQL.

Every error names the DÉTOUR table and id only, never a name, an email or a review text, so
the import's output can be pasted into an issue.
"""

import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid5

from novoya_api.catalog.domain import (
    Extra,
    ExtraPricing,
    Offer,
    OfferKind,
    Partner,
    PartnerKind,
    PriceUnit,
    Review,
    normalize_tags,
)
from novoya_api.catalog.infrastructure.countries import canonical_country
from novoya_api.catalog.infrastructure.db.models import DETOUR_SOURCE
from novoya_api.shared.domain.errors import InvalidInput

Row = Mapping[str, Any]

# Fixed forever: the ids of imported rows are derived from it, so a second import updates
# the same rows instead of adding new ones.
NAMESPACE = UUID("5f0c3a1e-8b7d-4c2a-9e61-0d7a4b9c2f18")

KINDS = {"hebergement": "hotel", "transport": "transport", "activite": "activity"}
PRICE_UNITS = {
    "personne/nuit": PriceUnit.PERSON_NIGHT,
    "personne/trajet": PriceUnit.PERSON_TRIP,
    "personne/activité": PriceUnit.PERSON_ACTIVITY,
}
PRICINGS = {
    "incluse": ExtraPricing.INCLUDED,
    "supplement": ExtraPricing.SUPPLEMENT,
    "sur_devis": ExtraPricing.ON_QUOTE,
}
SOURCE = DETOUR_SOURCE  # partners.source of imported partners


class DetourImportError(Exception):
    """The export has a row Novoya cannot take. Nothing was written."""


@dataclass(frozen=True)
class Place:
    country: str  # English
    city: str


@dataclass(frozen=True)
class DetourCatalog:
    partners: tuple[Partner, ...]
    offers: tuple[Offer, ...]
    reviews: tuple[Review, ...]
    extras: tuple[Extra, ...]


def detour_id(table: str, source_id: str) -> UUID:
    """The same Novoya id for the same DÉTOUR row on every import; different per table."""
    return uuid5(NAMESPACE, f"{table}:{source_id}")


def slugify(text: str) -> str:
    """ASCII id for a tag: "Surf & océan" -> "surf-ocean". Empty when nothing is left."""
    # Accents go; anything else that is not a letter or a digit (’ , & —) splits words.
    letters = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(
        char if char.isascii() else " " for char in letters if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def place(row: Row) -> Place:
    country = canonical_country(row["pays"] or "")
    if country is None:
        raise DetourImportError(f"destinations {row['id']}: country is not in the country map")
    city = " ".join((row["nom"] or "").split())
    if not city:
        raise DetourImportError(f"destinations {row['id']}: the city is empty")
    _fits("destinations", row["id"], city, 64)
    return Place(country, city)


def partner(row: Row, places: Mapping[str, Place]) -> Partner:
    where = _place_of("partenaires", row, places)
    _fits("partenaires", row["id"], row["nom"], 255)
    return _checked(
        "partenaires",
        row["id"],
        lambda: Partner(
            id=detour_id("partenaires", row["id"]),
            name=(row["nom"] or "").strip(),
            kind=PartnerKind(_kind("partenaires", row)),
            country=where.country,
            city=where.city,
            contact_email=(row["contact_email"] or "").strip(),
            contact_phone=None,
            active=row["statut"] == "actif",
        ),
    )


def offer(
    row: Row,
    places: Mapping[str, Place],
    months: Sequence[int],
    strengths: Sequence[str],
) -> Offer:
    source_id = row["id"]
    where = _place_of("offres", row, places)
    kind = OfferKind(_kind("offres", row))
    _fits("offres", source_id, row["nom"], 255)
    price, unit = _price(row)
    return _checked(
        "offres",
        source_id,
        lambda: Offer(
            id=detour_id("offres", source_id),
            partner_id=detour_id("partenaires", row["partenaire_id"]),
            kind=kind,
            title=(row["nom"] or "").strip(),
            description=(row["description"] or "").strip(),
            country=where.country,
            city=where.city,
            min_persons=1,
            max_persons=row["capacite"] or 0,
            available_from=date.fromisoformat(row["validite_debut"]),
            available_to=date.fromisoformat(row["validite_fin"]),
            tags=normalize_tags(_tags(kind, row["nom"] or "", strengths)),
            featured=False,
            active=True,
            price_eur=price,
            price_unit=unit,
            opening_months=tuple(sorted(set(months))),
            conditions=_text(row["conditions"]),
            restrictions=_text(row["restrictions"]),
            cancellation=_text(row["annulation"]),
            confirmation_delay_hours=row["delai_confirmation_heures"],
        ),
    )


def review(row: Row, places: Mapping[str, Place]) -> Review:
    """A row of avis_diffusables, with the destination of its circuit (no circuit is kept)."""
    where = places.get(row["destination_id"]) if row["destination_id"] else None
    if where is None:
        raise DetourImportError(f"avis {row['id']}: its circuit has no known destination")
    _fits("avis", row["id"], row["auteur"], 64)
    return _checked(
        "avis",
        row["id"],
        lambda: Review(
            id=detour_id("avis", row["id"]),
            country=where.country,
            city=where.city,
            rating=row["note"],
            reviewed_on=date.fromisoformat(row["date"]),
            text=row["texte"] or "",
            author=row["auteur"] or "",
        ),
    )


def extra(row: Row, constraints: Sequence[str]) -> Extra:
    source_id = row["id"]
    pricing = PRICINGS.get(row["tarification"])
    if pricing is None:
        raise DetourImportError(f"preferences {source_id}: unknown pricing")
    _fits("preferences", source_id, row["categorie"], 64)
    _fits("preferences", source_id, row["libelle"], 255)
    _fits("preferences", source_id, row["unite"], 64)
    return _checked(
        "preferences",
        source_id,
        lambda: Extra(
            id=detour_id("preferences", source_id),
            category=(row["categorie"] or "").strip(),
            label=(row["libelle"] or "").strip(),
            description=(row["description"] or "").strip(),
            pricing=pricing,
            supplement_eur=row["supplement_eur"],
            unit=(row["unite"] or "").strip(),
            constraints=tuple(constraints),
            active=True,
        ),
    )


def _kind(table: str, row: Row) -> str:
    kind = KINDS.get(row["type"])
    if kind is None:
        raise DetourImportError(f"{table} {row['id']}: unknown type")
    return kind


def _place_of(table: str, row: Row, places: Mapping[str, Place]) -> Place:
    where = places.get(row["destination_id"])
    if where is None:
        raise DetourImportError(f"{table} {row['id']}: unknown destination")
    return where


def _price(row: Row) -> tuple[int | None, PriceUnit | None]:
    if row["prix_unitaire_eur"] is None:
        return None, None
    unit = PRICE_UNITS.get(row["unite"])
    if unit is None:
        raise DetourImportError(f"offres {row['id']}: unknown price unit")
    return row["prix_unitaire_eur"], unit


def _tags(kind: OfferKind, title: str, strengths: Sequence[str]) -> list[str]:
    """The kind's tag (accommodation:stay, transport:transfer, or for an activity its name:
    the title before " - ", which is the place), then the destination's strengths as styles.

    Every offer carries the styles, so a wish that picks only a style still finds a bed and
    a transfer there."""
    if kind is OfferKind.HOTEL:
        tags = ["accommodation:stay"]
    elif kind is OfferKind.TRANSPORT:
        tags = ["transport:transfer"]
    else:
        tags = [f"activities:{slugify(title.split(' - ')[0])}"]
    tags += [f"style:{slugify(strength)}" for strength in strengths]
    return [tag for tag in tags if not tag.endswith(":")]


def _text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _fits(table: str, source_id: str, value: str | None, limit: int) -> None:
    if value is not None and len(value) > limit:
        raise DetourImportError(f"{table} {source_id}: a text is longer than {limit} characters")


def _checked[T](table: str, source_id: str, build: Callable[[], T]) -> T:
    """Builds the entity; a broken rule becomes an import error that names the row only."""
    try:
        return build()
    except InvalidInput as error:  # domain messages never carry the row's values
        raise DetourImportError(f"{table} {source_id}: {error}") from None
    except (ValueError, TypeError) as error:  # a bad date or number: its message may quote it
        raise DetourImportError(f"{table} {source_id}: {type(error).__name__}") from None
