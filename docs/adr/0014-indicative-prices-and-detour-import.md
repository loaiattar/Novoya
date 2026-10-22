# 0014. Indicative partner prices, and the DÉTOUR catalog import

- **Status:** Accepted
- **Date:** 2026-10-21
- **Issue / PR:** #83, #119

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
- An admin hides a partner, offer or extra with `hidden` (the catalog routes are admin
  only, #127); it is left out everywhere an inactive one is (search, coverage, tags,
  `GET /offers/{id}`, `GET /extras`, the extras of a quote request) and stays hidden after
  every import. An admin hides a review the same way: it leaves `GET /reviews` at once. A
  phone added in Novoya can no longer be erased by the import, since an imported partner's
  phone cannot be edited.
- The import is idempotent (ids are uuid5 of the DÉTOUR ids), runs in one transaction, opens
  the file read-only, prints counts only, and its errors name DÉTOUR ids, never a name or
  an email. The export itself is never committed (`*.sqlite`, `livraison/` in `.gitignore`).
- The privacy page (#45) must list published reviews (ARCHITECTURE §9).
- Tests: `tests/test_catalog_detour_mapping.py`, `tests/test_catalog_detour_sql.py`, on a
  made-up export (`tests/detour_fixture.py`).
