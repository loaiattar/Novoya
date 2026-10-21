"""Country names in French or English, to the English name Novoya stores.

Every country comes from the CLDR names that Babel ships, so a country the client adds later is
translated with no code change. COUNTRIES keeps the English names of the 86 countries of the first
DÉTOUR export: imported rows already use them, and they win over CLDR ("Ivory Coast", not
"Côte d’Ivoire"). A name that is not a country stops the import: it is never guessed."""

import unicodedata

from babel import Locale

COUNTRIES: dict[str, str] = {
    "Afrique du Sud": "South Africa",
    "Albanie": "Albania",
    "Argentine": "Argentina",
    "Arménie": "Armenia",
    "Australie": "Australia",
    "Autriche": "Austria",
    "Belgique": "Belgium",
    "Belize": "Belize",
    "Bolivie": "Bolivia",
    "Bosnie-Herzégovine": "Bosnia and Herzegovina",
    "Botswana": "Botswana",
    "Bulgarie": "Bulgaria",
    "Bénin": "Benin",
    "Cambodge": "Cambodia",
    "Canada": "Canada",
    "Chili": "Chile",
    "Chine": "China",
    "Chypre": "Cyprus",
    "Colombie": "Colombia",
    "Corée du Sud": "South Korea",
    "Costa Rica": "Costa Rica",
    "Croatie": "Croatia",
    "Cuba": "Cuba",
    "Côte d’Ivoire": "Ivory Coast",
    "Danemark": "Denmark",
    "Espagne": "Spain",
    "Estonie": "Estonia",
    "Fidji": "Fiji",
    "Finlande": "Finland",
    "France": "France",
    "Ghana": "Ghana",
    "Grèce": "Greece",
    "Guatemala": "Guatemala",
    "Géorgie": "Georgia",
    "Inde": "India",
    "Indonésie": "Indonesia",
    "Islande": "Iceland",
    "Italie": "Italy",
    "Japon": "Japan",
    "Kenya": "Kenya",
    "Laos": "Laos",
    "Lettonie": "Latvia",
    "Liban": "Lebanon",
    "Lituanie": "Lithuania",
    "Luxembourg": "Luxembourg",
    "Macédoine du Nord": "North Macedonia",
    "Madagascar": "Madagascar",
    "Malaisie": "Malaysia",
    "Malte": "Malta",
    "Maroc": "Morocco",
    "Maurice": "Mauritius",
    "Mexique": "Mexico",
    "Mongolie": "Mongolia",
    "Namibie": "Namibia",
    "Nicaragua": "Nicaragua",
    "Norvège": "Norway",
    "Nouvelle-Zélande": "New Zealand",
    "Népal": "Nepal",
    "Oman": "Oman",
    "Ouganda": "Uganda",
    "Ouzbékistan": "Uzbekistan",
    "Panama": "Panama",
    "Pays-Bas": "Netherlands",
    "Portugal": "Portugal",
    "Pérou": "Peru",
    "Roumanie": "Romania",
    "Royaume-Uni": "United Kingdom",
    "Rwanda": "Rwanda",
    "Samoa": "Samoa",
    "Serbie": "Serbia",
    "Slovénie": "Slovenia",
    "Sri Lanka": "Sri Lanka",
    "Suisse": "Switzerland",
    "Suède": "Sweden",
    "Sénégal": "Senegal",
    "Tanzanie": "Tanzania",
    "Taïwan": "Taiwan",
    "Thaïlande": "Thailand",
    "Togo": "Togo",
    "Tunisie": "Tunisia",
    "Vietnam": "Vietnam",
    "Zambie": "Zambia",
    "Égypte": "Egypt",
    "Équateur": "Ecuador",
    "États-Unis": "United States",
    "Éthiopie": "Ethiopia",
}


def country_key(name: str) -> str:
    """One spelling for lookups: spaces collapsed, case, accents and apostrophe style ignored."""
    decomposed = unicodedata.normalize("NFKD", name.replace("’", "'"))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(plain.split()).casefold()


# CLDR territory codes that are not countries: Europe, the eurozone, the UN, test codes.
_NOT_COUNTRIES = {"EU", "EZ", "QO", "UN", "XA", "XB", "ZZ"}


def _cldr_codes() -> dict[str, str]:
    """Country name (French or English) -> two-letter code."""
    codes: dict[str, str] = {}
    for language in ("en", "fr"):
        for code, name in Locale(language).territories.items():
            if len(code) == 2 and code.isalpha() and code not in _NOT_COUNTRIES:
                codes[country_key(name)] = code
    return codes


def _lookup() -> dict[str, str]:
    codes = _cldr_codes()
    english = {code: Locale("en").territories[code] for code in set(codes.values())}
    for french, detour_english in COUNTRIES.items():
        code = codes.get(country_key(french)) or codes.get(country_key(detour_english))
        if code:
            english[code] = detour_english
    names = {key: english[code] for key, code in codes.items()}
    # DÉTOUR spellings that CLDR writes differently ("Ivory Coast", "Bosnia and Herzegovina").
    for french, detour_english in COUNTRIES.items():
        names[country_key(french)] = detour_english
        names[country_key(detour_english)] = detour_english
    return names


_ENGLISH = _lookup()


def canonical_country(name: str) -> str | None:
    """The English name of a country written in French or in English, any case, or None."""
    return _ENGLISH.get(country_key(name))
