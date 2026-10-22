# 0014. Indicative partner prices, and the DÉTOUR catalog import

- **Status:** Accepted
- **Date:** 2026-10-21
- **Issue / PR:** #83, #119, #132

## Context

The client, DÉTOUR, sent its catalog as a sqlite export: destinations, partners, offers with
a unit price, opening months and terms, travellers' reviews behind consents, trip options
(`preferences`), and also circuits, advisors and test scenarios. Partners do publish a unit
price per person, but the price of a trip is still negotiated (ADR 0006). The reviews are
personal data: ADR 0003 asks for a GDPR review before Novoya reads outside data. Country
names in the export are in French; Novoya stores English names.

## Decision

We import partners, offers, publishable reviews and extras with
`python -m novoya_api.catalog.infrastructure.detour --source detour.sqlite`, and nothing else.
An admin can run the same import from the back office (#132): see below.

- **Indicative prices on the offer page only.** An offer keeps its unit price (`price_eur`,
  `price_unit` per person per night, trip or activity) and shows it as indicative on
  `GET /offers/{id}`. The plan, the agent's prices and the quote are unchanged: the agent
  still negotiates each item, and the total comes from those negotiated prices.
- **Reviews only from `avis_diffusables`.** That view holds the reviews whose author agreed
  to publication, already pseudonymised ("First name I." or "Voyageur anonyme"). The tables
  `avis`, `avis_publics` and `consentements` are never read. Each import replaces the
  reviews: a review whose consent was withdrawn is deleted on the next import. This is the
  GDPR review ADR 0003 asks for.
- **Not imported:** circuits, advisors, scenarios, raw reviews and consents.
- **Countries in English** (`catalog/infrastructure/countries.py`). Any country written in
  French or in English is found through the CLDR names that Babel ships, so a country the
  client adds later needs no code change. The 86 names of the first export keep their English spelling ("Ivory Coast").
  A name that is not a country stops the import. Cities are kept as given.
- Partners have no phone in the export: `contact_phone` is optional. Imported partners are
  marked `source = 'detour'`, and the development seed refuses to run after an import.
- An admin can hide a published review in Novoya (`hidden` on `reviews`). The import never
  writes that column, so a hidden review stays hidden after the next export. A review that
  left `avis_diffusables` is still deleted.
- Extras (`included`, `supplement`, `on_quote`) can be added when the client asks for a
  quote. A supplement is counted once, at its amount then; the agent prices `on_quote`
  extras and can adjust a supplement. A supplement whose unit is per person, per night or
  per day (`par personne`, `par nuit`, `par personne et nuit`, `par jour`,
  `par demi-journée`, a fixed list) is flagged `needs_quantity_check`: the plan is not
  ready to quote until the assigned agent confirms it by setting its price, even the same.
- **DÉTOUR owns imported rows.** A partner with `source = 'detour'`, its offers and every
  extra are written by the import and changed in DÉTOUR. Novoya owns only `featured`
  (offers) and `hidden` (partners, offers, extras, reviews), which the import never writes.

## Consequences

- ADR 0006 is partly replaced: offers may carry a price, but only as an indication.
- A partner, offer or extra that leaves the export is made inactive, not deleted (plans may
  point to it), and active again when it comes back. The export owns `active`.
- The admin API refuses to change an imported row's content with 409 `imported_row`, whose
  message says to change it in DÉTOUR: name, kind, place, contact and `active` of a
  partner; anything but `featured` and `hidden` of its offers; adding an offer to it. An
  extra only takes `hidden` (`PATCH /admin/extras/{id}`). A review only takes `hidden`
  (`PATCH /admin/reviews/{id}`). There is no delete. Sending a
  row its own values is not a change. Hand-made partners and offers stay fully editable.
- An agent hides a partner, offer or extra with `hidden`; it is left out everywhere an
  inactive one is (search, coverage, tags, `GET /offers/{id}`, `GET /extras`, the extras of
  a quote request) and stays hidden after every import. An admin hides a review the same
  way: it leaves `GET /reviews` at once. A phone added in Novoya can no longer be erased by
  the import, since an imported partner's phone cannot be edited.
- The import is idempotent (ids are uuid5 of the DÉTOUR ids), runs in one transaction, opens
  the file read-only, prints counts only, and its errors name DÉTOUR ids, never a name or
  an email. The export itself is never committed (`*.sqlite`, `livraison/` in `.gitignore`).
- **Import from the back office (#132).** An admin uploads the export on `/admin/import`;
  `POST /admin/catalog/import` (admins only) takes the raw file and runs `import_detour`, the
  code of the command line, and answers the counts. Since the file holds partner contacts
  and reviews, and comes from a browser:
  - it is written to a new temporary folder (mode 0700) under a name the server picks, the
    browser's file name is never used, and the folder is deleted after the import, whether it
    worked or not. Nothing is kept or committed, and nothing relies on Render's disk (ADR 0013);
  - it must start with the sqlite header (`not_a_detour_export`, 422), and stay under
    `NOVOYA_DETOUR_MAX_BYTES`, 20 MB by default: the upload stops as soon as it passes it
    (413);
  - sqlite opens it read-only, with `query_only` on and `trusted_schema` off; extensions
    stay off;
  - one import at a time: the import's transaction takes a PostgreSQL advisory lock, so a
    second one, from the back office or the command line, stops with `import_running` (409)
    instead of waiting;
  - a refused row answers `detour_import_failed` (422) with the DÉTOUR table and id only.
  - `avis_diffusables` is a view defined in the file itself. A hand-made file could make it
    read the raw reviews; we accept it because only admins import, and the file is the one
    the client sent.
- The privacy page (#45) must list published reviews (ARCHITECTURE §9).
- Tests: `tests/test_catalog_detour_mapping.py`, `tests/test_catalog_detour_sql.py`,
  `tests/test_catalog_import.py`, on a made-up export (`tests/detour_fixture.py`).
