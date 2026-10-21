"""A made-up DÉTOUR export, built with sqlite3 in a test folder.

Same tables and the same avis_diffusables view as the client's file (line breaks aside), but
every row is invented: never copy names, emails, reviews or authors from the real export here.
"""

import sqlite3
from pathlib import Path
from types import TracebackType

SCHEMA = """
CREATE TABLE destinations ("id" TEXT PRIMARY KEY, "nom" TEXT, "pays" TEXT, "region" TEXT,
  "duree_min_jours" INTEGER, "duree_max_jours" INTEGER, "budget_min_eur" INTEGER,
  "budget_max_eur" INTEGER, "difficulte" INTEGER, "description" TEXT);
CREATE TABLE destinations_atouts ("parent_id" TEXT REFERENCES "destinations"(id),
  "position" INTEGER, "valeur" TEXT, PRIMARY KEY(parent_id, position));
CREATE TABLE voyages ("id" TEXT PRIMARY KEY, "destination_id" TEXT REFERENCES "destinations"(id),
  "nom" TEXT, "duree_jours" INTEGER, "budget_eur_personne" INTEGER, "difficulte" INTEGER,
  "description" TEXT);
CREATE TABLE preferences ("id" TEXT PRIMARY KEY, "categorie" TEXT, "libelle" TEXT,
  "description" TEXT, "tarification" TEXT, "supplement_eur" INTEGER, "unite" TEXT);
CREATE TABLE preferences_contraintes ("parent_id" TEXT REFERENCES "preferences"(id),
  "position" INTEGER, "valeur" TEXT, PRIMARY KEY(parent_id, position));
CREATE TABLE avis ("id" TEXT PRIMARY KEY, "voyage_id" TEXT REFERENCES "voyages"(id),
  "prenom" TEXT, "initiale" TEXT, "note" INTEGER CHECK("note" BETWEEN 1 AND 5), "date" TEXT,
  "texte" TEXT, "publication" TEXT, "consentement_id" TEXT REFERENCES "consentements"(id));
CREATE TABLE consentements ("id" TEXT PRIMARY KEY, "avis_id" TEXT REFERENCES "avis"(id),
  "portee" TEXT, "statut" TEXT, "date" TEXT, "preuve_ref" TEXT, "note_interne" TEXT);
CREATE TABLE partenaires ("id" TEXT PRIMARY KEY, "destination_id" TEXT
  REFERENCES "destinations"(id), "nom" TEXT, "type" TEXT, "description" TEXT,
  "contact_email" TEXT, "delai_reponse_heures" INTEGER, "statut" TEXT);
CREATE TABLE offres ("id" TEXT PRIMARY KEY, "partenaire_id" TEXT REFERENCES "partenaires"(id),
  "destination_id" TEXT REFERENCES "destinations"(id), "nom" TEXT, "type" TEXT,
  "description" TEXT, "prix_unitaire_eur" INTEGER CHECK("prix_unitaire_eur" >= 0), "unite" TEXT,
  "capacite" INTEGER CHECK("capacite" >= 0), "validite_debut" TEXT, "validite_fin" TEXT,
  "conditions" TEXT, "restrictions" TEXT, "delai_confirmation_heures" INTEGER,
  "annulation" TEXT);
CREATE TABLE offres_mois_disponibles ("parent_id" TEXT REFERENCES "offres"(id),
  "position" INTEGER, "valeur" INTEGER, PRIMARY KEY(parent_id, position));
CREATE TABLE avis_publics ("id" TEXT PRIMARY KEY, "voyage_id" TEXT REFERENCES "voyages"(id),
  "note" INTEGER CHECK("note" BETWEEN 1 AND 5), "date" TEXT, "texte" TEXT, "auteur" TEXT);
CREATE VIEW avis_diffusables AS SELECT a.id,a.voyage_id,a.note,a.date,a.texte,
CASE WHEN a.publication='nominatif' AND c.portee='nom_et_avis'
THEN a.prenom || ' ' || a.initiale || '.'
ELSE 'Voyageur anonyme' END AS auteur
FROM avis a JOIN consentements c ON c.id=a.consentement_id
WHERE c.statut='accorde' AND c.portee IN ('nom_et_avis','avis_anonyme')
AND a.publication<>'interdit';
"""


class DetourFile:
    """Writes made-up DÉTOUR rows. Creates the tables when the file is new.

    Use it as a context manager: the rows are committed and the file closed on exit."""

    def __init__(self, path: Path) -> None:
        new = not path.exists()
        self.path = path
        self.connection = sqlite3.connect(path)
        if new:
            self.connection.executescript(SCHEMA)

    def __enter__(self) -> "DetourFile":
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        if kind is None:
            self.connection.commit()
        self.connection.close()

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.connection.execute(sql, params)

    def destination(self, id: str, nom: str, pays: str, atouts: tuple[str, ...] = ()) -> None:
        self.execute(
            "INSERT INTO destinations (id, nom, pays, description) VALUES (?, ?, ?, ?)",
            (id, nom, pays, "Destination de test"),
        )
        for position, valeur in enumerate(atouts):
            self.execute("INSERT INTO destinations_atouts VALUES (?, ?, ?)", (id, position, valeur))

    def partner(
        self,
        id: str,
        destination_id: str,
        *,
        nom: str = "Partenaire inventé",
        type: str = "hebergement",
        contact_email: str = "contact@partenaire.example",
        statut: str = "actif",
    ) -> None:
        self.execute(
            "INSERT INTO partenaires (id, destination_id, nom, type, description, contact_email,"
            " delai_reponse_heures, statut) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (id, destination_id, nom, type, "Partenaire de test", contact_email, 24, statut),
        )

    def offer(
        self,
        id: str,
        partner_id: str,
        destination_id: str,
        *,
        nom: str = "Offre inventée",
        type: str = "hebergement",
        description: str = "Une offre de test",
        prix: int | None = 50,
        unite: str = "personne/nuit",
        capacite: int = 2,
        debut: str = "2026-11-01",
        fin: str = "2027-10-31",
        conditions: str | None = None,
        restrictions: str | None = None,
        delai: int | None = None,
        annulation: str | None = None,
        months: tuple[int, ...] = (),
    ) -> None:
        self.execute(
            "INSERT INTO offres (id, partenaire_id, destination_id, nom, type, description,"
            " prix_unitaire_eur, unite, capacite, validite_debut, validite_fin, conditions,"
            " restrictions, delai_confirmation_heures, annulation)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                id,
                partner_id,
                destination_id,
                nom,
                type,
                description,
                prix,
                unite,
                capacite,
                debut,
                fin,
                conditions,
                restrictions,
                delai,
                annulation,
            ),
        )
        for position, valeur in enumerate(months):
            self.execute(
                "INSERT INTO offres_mois_disponibles VALUES (?, ?, ?)", (id, position, valeur)
            )

    def voyage(self, id: str, destination_id: str) -> None:
        self.execute(
            "INSERT INTO voyages (id, destination_id, nom, duree_jours, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (id, destination_id, "Circuit inventé", 7, "Un circuit de test"),
        )

    def review(
        self,
        id: str,
        voyage_id: str,
        *,
        prenom: str,
        initiale: str,
        note: int,
        date: str,
        texte: str,
        publication: str,
        portee: str,
        statut: str,
    ) -> None:
        consent_id = f"C{id}"
        self.execute(
            "INSERT INTO consentements (id, avis_id, portee, statut, date) VALUES (?, ?, ?, ?, ?)",
            (consent_id, id, portee, statut, date),
        )
        self.execute(
            "INSERT INTO avis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (id, voyage_id, prenom, initiale, note, date, texte, publication, consent_id),
        )

    def public_review(
        self, id: str, voyage_id: str, *, note: int, date: str, texte: str, auteur: str
    ) -> None:
        self.execute(
            "INSERT INTO avis_publics VALUES (?, ?, ?, ?, ?, ?)",
            (id, voyage_id, note, date, texte, auteur),
        )

    def preference(
        self,
        id: str,
        *,
        categorie: str = "confort",
        libelle: str = "Option inventée",
        description: str = "Une option de test",
        tarification: str = "incluse",
        supplement_eur: int | None = None,
        unite: str = "par séjour",
        constraints: tuple[tuple[int, str], ...] = (),
    ) -> None:
        self.execute(
            "INSERT INTO preferences VALUES (?, ?, ?, ?, ?, ?, ?)",
            (id, categorie, libelle, description, tarification, supplement_eur, unite),
        )
        for position, valeur in constraints:
            self.execute(
                "INSERT INTO preferences_contraintes VALUES (?, ?, ?)", (id, position, valeur)
            )


# The made-up export most tests start from.
CHANIA = "D001"
LUZ = "D002"
CHANIA_STAY = "F001"
CHANIA_TRANSFER = "F002"
LUZ_MUSEUM = "F003"
SECRET_PARTNER_NAME = "Maison Zéphyr Inventée"
SECRET_PARTNER_EMAIL = "zephyr@partenaire.example"


def sample_detour(path: Path) -> Path:
    """Two destinations, three partners (one inactive), three offers, four reviews behind
    consents (one refused), one old public review, three extras."""
    with DetourFile(path) as detour:
        detour.destination(CHANIA, "Chania", "Grèce", ("Plages secrètes", "Cuisine crétoise"))
        detour.destination(LUZ, " Saint-Jean  de Luz ", "France", ("Surf & océan", "—"))

        detour.partner(
            "P001",
            CHANIA,
            nom=SECRET_PARTNER_NAME,
            type="hebergement",
            contact_email=SECRET_PARTNER_EMAIL,
        )
        detour.partner("P002", CHANIA, nom="Navette Inventée", type="transport")
        detour.partner("P003", LUZ, nom="Atelier Inventé", type="activite", statut="inactif")

        detour.offer(
            CHANIA_STAY,
            "P001",
            CHANIA,
            nom="Chania - nuit en chambre double",
            type="hebergement",
            description="Une chambre double près du port",
            prix=85,
            unite="personne/nuit",
            capacite=2,
            debut="2026-11-01",
            fin="2027-10-31",
            conditions="Petit-déjeuner inclus",
            restrictions="Non-fumeur",
            delai=24,
            annulation="Gratuite jusqu'à 7 jours avant",
            months=(9, 5, 6, 5),
        )
        detour.offer(
            CHANIA_TRANSFER,
            "P002",
            CHANIA,
            nom="Transfert aéroport - Chania",
            type="transport",
            prix=30,
            unite="personne/trajet",
            capacite=8,
            months=(3, 4),
        )
        detour.offer(
            LUZ_MUSEUM,
            "P003",
            LUZ,
            nom="Musée national - Saint-Jean de Luz",
            type="activite",
            prix=15,
            unite="personne/activité",
            capacite=12,
            months=(7,),
        )

        detour.voyage("V001", CHANIA)
        detour.voyage("V002", LUZ)
        detour.review(
            "A001",
            "V001",
            prenom="Zélie",
            initiale="Q",
            note=5,
            date="2026-06-01",
            texte="Un séjour parfait, inventé pour les tests.",
            publication="nominatif",
            portee="nom_et_avis",
            statut="accorde",
        )
        detour.review(
            "A002",
            "V002",
            prenom="Ombeline",
            initiale="X",
            note=4,
            date="2026-07-15",
            texte="Très bon accueil, inventé aussi.",
            publication="anonyme",
            portee="avis_anonyme",
            statut="accorde",
        )
        detour.review(
            "A003",
            "V001",
            prenom="Testine",
            initiale="R",
            note=2,
            date="2026-05-01",
            texte="Un avis sans consentement.",
            publication="nominatif",
            portee="aucune",
            statut="refuse",
        )
        detour.review(
            "A004",
            "V001",
            prenom="Ombeline",
            initiale="X",
            note=3,
            date="2026-08-20",
            texte="Plus récent, inventé.",
            publication="anonyme",
            portee="avis_anonyme",
            statut="accorde",
        )
        detour.public_review(
            "AP01", "V001", note=1, date="2026-09-01", texte="Ancienne table.", auteur="Ancien X."
        )

        detour.preference(
            "O001",
            categorie="hebergement",
            libelle="Chambre calme",
            description="Loin de l'ascenseur",
            tarification="incluse",
            unite="par séjour",
            constraints=((1, "Demande à l'avance"), (0, "Selon disponibilité")),
        )
        detour.preference(
            "O002",
            categorie="transport",
            libelle="Bagage en plus",
            description="Un bagage en soute de plus",
            tarification="supplement",
            supplement_eur=25,
            unite="par bagage",
        )
        detour.preference(
            "O003",
            categorie="activite",
            libelle="Guide privé",
            description="Un guide pour le groupe",
            tarification="sur_devis",
            unite="par activité",
            constraints=((0, "Trois jours de préavis"),),
        )
    return path
