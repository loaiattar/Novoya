# `apps/web/brand/` — DÉTOUR agency data

Material extracted from the old showcase site (`detour-main`, static HTML from 2013), gathered here so the new front can reuse it. This folder holds extracted material, not app code. The next ticket wires it into `src/`.

```
brand/
├── agency.json          the data: every value has its `source` and `status`
├── agency.schema.json   JSON Schema (draft 2020-12) for agency.json
├── images/
│   ├── logo.png         1536×512 PNG, original from detour-main/brand/
│   └── favicon.png      512×512 PNG, « D » symbol, original from detour-main/brand/
└── README.md            this file
```

## How to read `agency.json`

Each entry looks like this:

```json
"email": {
  "value": "contact@detour-voyages.fr",
  "source": "site/*.html (footer mailto), site/contact.html (form action), README.md",
  "status": "confirmed"
}
```

- `value`: the data itself. Translated texts are `{ "fr": …, "en": … }`. Facts (address, numbers, links, hours) are never translated.
- `source`: the file in the old repo (and where in it) the value comes from.
- `status`: `confirmed` (found and consistent in the old repo) or `to_check` (found, but possibly outdated, placeholder or not yet validated).
- `translation_status.en`: the FR texts are verbatim from the old site. The EN versions are new drafts and are all `to_check`.
- `note`: why a value is `to_check`, or anything the implementer should know.

Validate after any edit:

```bash
npx ajv-cli validate --spec=draft2020 -c ajv-formats -s apps/web/brand/agency.schema.json -d apps/web/brand/agency.json
# or
python3 -c "import json,jsonschema as j; s=json.load(open('apps/web/brand/agency.schema.json')); j.Draft202012Validator(s, format_checker=j.Draft202012Validator.FORMAT_CHECKER).validate(json.load(open('apps/web/brand/agency.json')))"
```

## Rules for the next ticket

1. **Never publish a `to_check` value.** Until it is confirmed, hide the element or show nothing in its place. Do not show a placeholder that looks like real data. This applies first to the Atout France number.
2. **Don't translate facts.** The address, phone, e-mail, hours, legal numbers and company names are the same in FR and EN. Only the presentation (day names, phone formatting) is localised, by the front.
3. **Optimise images when they are used, not here.** `images/` keeps the originals. The build or the front generates the sizes and formats it needs (WebP/AVIF, responsive `srcset`, favicon sizes). Don't commit resized copies in `brand/`.
4. **Only images the agency owns.** Every entry in `images` has `rights: "agency"`, and the schema enforces it. Don't add a photo without written proof of rights (see "Excluded images").
5. **No staff personal data.** No staff names, direct e-mails or direct phone numbers without the person's written consent. Use the generic mailbox and the agency phone number.
6. **Legal texts are not copied.** The new mentions légales and CGV are written from the facts in `legal`, not from old texts (the old site had none anyway).

## Where each piece of data goes

| Data (`agency.json` path) | Status | Where in the new site |
|---|---|---|
| `identity.trade_name` | confirmed | `<title>` suffix, Open Graph `og:site_name`, logo `alt`, schema.org `TravelAgency.name` |
| `identity.display_name` | confirmed | Footer contact block, © line, mentions légales (« Éditeur ») |
| `identity.founded_year` | confirmed | About page, optional footer « depuis 2012 » |
| `identity.website` | confirmed | Canonical URLs, sitemap, Open Graph `og:url`, schema.org `url` |
| `identity.tagline` | confirmed (EN to_check) | Header next to the logo or home `<title>`, footer intro |
| `identity.logo_baseline` | confirmed (EN to_check) | Logo `alt` text only (already drawn in the logo) |
| `identity.slogan` | confirmed (EN to_check) | Home hero heading |
| `identity.description_short` | confirmed (EN to_check) | Footer « L'agence » column, Open Graph `og:description` |
| `identity.description_long` | confirmed (EN to_check) | Home intro section, About page |
| `identity.meta_description` | confirmed (EN to_check) | Home `<meta name="description">` (check the city list against the current offer) |
| `contact.address` | confirmed | Footer, contact page, mentions légales (siège), schema.org `address` |
| `contact.phone` | confirmed | Header « Appelez-nous », footer, contact page; `tel:` link built from `value` (E.164), text from `display` |
| `contact.email` | confirmed | Footer, contact page, quote form recipient, mentions légales |
| `contact.opening_hours` | **to_check** | Header top bar or contact page, schema.org `openingHoursSpecification` |
| `legal.atout_france_registration` | **to_check** | Footer legal line (« Immatriculation Atout France IM… »), mentions légales, CGV |
| `brand.colors` | **to_check** | Design tokens (CSS variables / Tailwind theme), only if they match Figma |
| `brand.fonts` | **to_check** | Font loading and design tokens, only if they match Figma |
| `images.logo` | confirmed | Header, footer, Open Graph image (on a background), e-mail templates |
| `images.favicon` | confirmed | Favicon + `apple-touch-icon` + PWA icons (generate 16/32/180/192/512 from this file) |
| `credits.web_agency` | to_check | Nowhere by default (it built the old site; it is not the host) |

## What is missing

These were looked for in the old repository and **not found**. The old site linked « Mentions légales », « CGV » and « Plan du site » to `#`, and the pages don't exist. They must be asked for from the agency before the mentions légales page can go live.

| Data | Required by | Where it will go |
|---|---|---|
| Company name (raison sociale) | LCEN | Mentions légales, CGV, footer |
| Legal form (SARL, SAS…) | LCEN, Code de commerce | Mentions légales |
| Share capital | Code de commerce R123-238 | Mentions légales |
| SIREN / SIRET | LCEN | Mentions légales, footer legal line |
| RCS (city + number) | Code de commerce | Mentions légales |
| Intra-EU VAT number | LCEN (commercial activity) | Mentions légales, CGV |
| **Real Atout France number** | Code du tourisme L211-18 | Footer, mentions légales, CGV (the one on the old site is marked « fictive ») |
| Financial guarantor (name, address) | Code du tourisme R211-26 | Mentions légales, CGV, pre-contract information |
| Professional liability insurer (name, address, contract n°) | Code du tourisme R211-35 | Mentions légales, CGV |
| Publication director | LCEN | Mentions légales (role, or name with consent) |
| Host (name, address, phone) | LCEN | Mentions légales |
| Map link | — | Contact page, footer (can be built once the address is confirmed) |
| Social media links | — | Header/footer icons. The old site showed Facebook, Twitter, Google+ and Pinterest, but every link was `#` (and Google+ no longer exists). Ask which accounts exist. |
| Logo as SVG | Ticket (preferred format) | Header/footer. Only a PNG exists. Ask the designer for the vector file. |
| EN translations validated | — | All `translation_status.en` values |

## Still `to_check`

| Value | Why |
|---|---|
| `contact.opening_hours` (Tue–Sat, 10:00–19:00) | Comes from a 2013 site. |
| `legal.atout_france_registration` (IM044120000) | The old site itself says « (fictive) ». |
| `brand.colors`, `brand.fonts` | To compare with the Figma mockup; Figma wins. |
| `credits.web_agency` | Only kept for the record. |
| All EN texts | New drafts, to be proofread. |

## Excluded images

The old repo's `brand/` folder also holds 5 photos (`slide-1.png`, `slide-2.png`, `nantes.png`, `lyon.png`, `lille.png`, with smaller JPG copies in `site/img/`). **They are not copied here**, because nothing in the repo proves the agency owns them: there are no credits, no licence file and no author metadata. Some have specific issues:

- `nantes.png` shows the Grand Éléphant of Les Machines de l'île. That is a protected artwork, and France has no commercial freedom-of-panorama exception, so commercial use needs the rights holder's permission.
- `slide-1.png` shows two identifiable people. Using it needs a model release (droit à l'image).
- `slide-2.png` (hotel room) and `lyon.png` / `lille.png` (city views) have no known author or licence.

If the agency provides proof of rights (a commissioned shoot, a stock licence, a generation licence), copy the original into `images/`, add an entry under `images` with `rights: "agency"` and the proof in `source`/`note`.

## Deliberately not kept

- **Staff data:** the first name and role of the founder, and the team description (`site/agence.html`). There is no consent to publish them.
- **Customer names in testimonials** (`site/index.html`). There is no consent, and testimonials should come from a verifiable source.
- **The Facebook widget** (« 1 248 personnes aiment ça »): a hard-coded number that can't be verified.
- **« © 2013 », « Meilleure vue en 1024x768 »**: outdated.
- **The form's privacy line** (« loi Informatique et Libertés du 6 janvier 1978 »): outdated. The new form needs a GDPR notice.
- **Destinations, prices and news** (Nantes / Lyon / Lille offers, « à partir de 179 € »): catalogue content, not agency identity. They are out of scope for this folder.
- **`conseillers/` (back-office)**: an internal tool with no public agency data to extract.
