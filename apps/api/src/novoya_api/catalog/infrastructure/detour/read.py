"""Reads the DÉTOUR sqlite export, read-only, and maps it with mapping.py.

Reviews come only from the view avis_diffusables: the reviews whose author agreed to
publication, already pseudonymised. The tables avis, avis_publics and consentements are never
read (ADR 0014). Circuits, advisors and scenarios are not imported either.
"""

import sqlite3
from collections import defaultdict
from pathlib import Path

from novoya_api.catalog.infrastructure.detour import mapping
from novoya_api.catalog.infrastructure.detour.mapping import DetourCatalog, DetourImportError


def open_source(path: Path) -> sqlite3.Connection:
    """The export, opened read-only: the import can never change the client's file.

    The file may come from an upload (#132), so it is not trusted either: no writes even
    through a view or a trigger, and no SQL functions with side effects in its schema.
    Extensions stay off, as Python leaves them."""
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA trusted_schema = OFF")
    return connection


def read_catalog(path: Path) -> DetourCatalog:
    """Every partner, offer, publishable review and extra. Raises DetourImportError on the
    first row Novoya cannot take."""
    connection = open_source(path)
    try:
        return _read(connection)
    except sqlite3.Error as error:
        raise DetourImportError(f"the export cannot be read: {type(error).__name__}") from None
    finally:
        connection.close()


def _read(connection: sqlite3.Connection) -> DetourCatalog:
    places = {
        row["id"]: mapping.place(row)
        for row in connection.execute("SELECT id, nom, pays FROM destinations ORDER BY id")
    }
    strengths = _lists(
        connection, "SELECT parent_id, valeur FROM destinations_atouts ORDER BY parent_id, position"
    )
    months = _lists(
        connection,
        "SELECT parent_id, valeur FROM offres_mois_disponibles ORDER BY parent_id, position",
    )
    constraints = _lists(
        connection,
        "SELECT parent_id, valeur FROM preferences_contraintes ORDER BY parent_id, position",
    )

    partners = tuple(
        mapping.partner(row, places)
        for row in connection.execute(
            "SELECT id, destination_id, nom, type, contact_email, statut FROM partenaires"
            " ORDER BY id"
        )
    )
    partner_ids = {partner.id for partner in partners}
    offers = []
    for row in connection.execute(
        "SELECT id, partenaire_id, destination_id, nom, type, description, prix_unitaire_eur,"
        " unite, capacite, validite_debut, validite_fin, conditions, restrictions,"
        " delai_confirmation_heures, annulation FROM offres ORDER BY id"
    ):
        if mapping.detour_id("partenaires", row["partenaire_id"] or "") not in partner_ids:
            raise DetourImportError(f"offres {row['id']}: unknown partner")
        offers.append(
            mapping.offer(
                row, places, months.get(row["id"], []), strengths.get(row["destination_id"], [])
            )
        )
    reviews = tuple(
        mapping.review(row, places)
        for row in connection.execute(
            "SELECT a.id, a.note, a.date, a.texte, a.auteur, v.destination_id"
            " FROM avis_diffusables a LEFT JOIN voyages v ON v.id = a.voyage_id ORDER BY a.id"
        )
    )
    extras = tuple(
        mapping.extra(row, constraints.get(row["id"], []))
        for row in connection.execute(
            "SELECT id, categorie, libelle, description, tarification, supplement_eur, unite"
            " FROM preferences ORDER BY id"
        )
    )
    return DetourCatalog(partners, tuple(offers), reviews, extras)


def _lists(connection: sqlite3.Connection, sql: str) -> dict[str, list]:
    """parent_id -> its values, in position order."""
    found: dict[str, list] = defaultdict(list)
    for parent_id, value in connection.execute(sql):
        found[parent_id].append(value)
    return found
