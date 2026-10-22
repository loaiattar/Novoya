// Partners and offers in the admin pages: the same checks as the API (catalog/presentation/
// http/schemas.py and domain/offer.py), and the bodies sent. Pure: errors are i18n keys of the
// `admin` namespace.

export type CatalogKind = 'hotel' | 'guide' | 'transport' | 'activity' | 'agency'
export type PriceUnit = 'person/night' | 'person/trip' | 'person/activity'

/** An offer as typed in the form: numbers stay text until they are checked. */
export type OfferFormValues = {
  kind: CatalogKind
  title: string
  description: string
  country: string
  city: string
  minPersons: string
  maxPersons: string
  /** yyyy-mm-dd, as a date input gives it. */
  availableFrom: string
  availableTo: string
  /** section:tag, separated by commas, spaces or lines. */
  tags: string
  featured: boolean
  active: boolean
  hidden: boolean
  price: string
  priceUnit: PriceUnit | ''
  openingMonths: number[]
  conditions: string
  restrictions: string
  cancellation: string
  confirmationDelayHours: string
}

export type PartnerFormValues = {
  name: string
  kind: CatalogKind
  country: string
  city: string
  contactEmail: string
  contactPhone: string
  active: boolean
  hidden: boolean
}

export type CatalogErrorKey =
  | 'errors.required'
  | 'errors.placeTooLong'
  | 'errors.textTooLong'
  | 'errors.phoneTooLong'
  | 'errors.email'
  | 'errors.tagsInvalid'
  | 'errors.tagsTooMany'
  | 'errors.minPersons'
  | 'errors.personsTooMany'
  | 'errors.maxBelowMin'
  | 'errors.datesInverted'
  | 'errors.priceInvalid'
  | 'errors.priceNeeded'
  | 'errors.unitNeeded'
  | 'errors.months'
  | 'errors.delayInvalid'

export type OfferFormErrors = Partial<Record<keyof OfferFormValues, CatalogErrorKey>>
export type PartnerFormErrors = Partial<Record<keyof PartnerFormValues, CatalogErrorKey>>

const PLACE_MAX = 64
const TEXT_MAX = 255
const PHONE_MAX = 32
const TAGS_MAX = 50
// The offers columns are int4; the API bounds them (schemas.py PRICE_MAX_EUR, DELAY_MAX_HOURS,
// PERSONS_MAX).
const PRICE_MAX = 1_000_000
const DELAY_MAX = 720
const PERSONS_MAX = 1_000
// Same ids as the API (domain/offer.py, _CATALOG_TAG).
const TAG = /^[a-z0-9]+(?:[_-][a-z0-9]+)*:[a-z0-9]+(?:[_-][a-z0-9]+)*$/
// Same pattern as the API's EmailText.
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
const WHOLE = /^\d+$/

/** The tags typed, lowercased and without duplicates; `invalid` are those not section:tag. */
export function parseTags(text: string): { tags: string[]; invalid: string[] } {
  const tags: string[] = []
  const invalid: string[] = []
  for (const raw of text.split(/[\s,]+/)) {
    const tag = raw.toLowerCase()
    if (!tag) continue
    const list = TAG.test(tag) ? tags : invalid
    if (!list.includes(tag)) list.push(tag)
  }
  return { tags, invalid }
}

/** Why each field of the offer would be refused. Empty when it can be sent. */
export function offerFormErrors(values: OfferFormValues): OfferFormErrors {
  const errors: OfferFormErrors = {}
  const title = text(values.title, TEXT_MAX, 'errors.textTooLong')
  if (title) errors.title = title
  if (!values.description.trim()) errors.description = 'errors.required'
  const country = text(values.country, PLACE_MAX, 'errors.placeTooLong')
  if (country) errors.country = country
  const city = text(values.city, PLACE_MAX, 'errors.placeTooLong')
  if (city) errors.city = city

  const min = wholeNumber(values.minPersons)
  if (min === undefined || min < 1) errors.minPersons = 'errors.minPersons'
  else if (min > PERSONS_MAX) errors.minPersons = 'errors.personsTooMany'
  const max = wholeNumber(values.maxPersons)
  if (max === undefined || max < Math.max(min ?? 1, 1)) errors.maxPersons = 'errors.maxBelowMin'
  else if (max > PERSONS_MAX) errors.maxPersons = 'errors.personsTooMany'

  if (!values.availableFrom) errors.availableFrom = 'errors.required'
  if (!values.availableTo) errors.availableTo = 'errors.required'
  else if (values.availableFrom && values.availableFrom > values.availableTo) errors.availableTo = 'errors.datesInverted'

  const tags = parseTags(values.tags)
  if (tags.invalid.length > 0) errors.tags = 'errors.tagsInvalid'
  else if (tags.tags.length > TAGS_MAX) errors.tags = 'errors.tagsTooMany'

  const price = values.price.trim()
  if (price) {
    const amount = wholeNumber(price)
    if (amount === undefined || amount <= 0 || amount > PRICE_MAX) errors.price = 'errors.priceInvalid'
    else if (!values.priceUnit) errors.priceUnit = 'errors.unitNeeded'
  } else if (values.priceUnit) {
    errors.price = 'errors.priceNeeded'
  }

  if (values.openingMonths.some((month) => !Number.isInteger(month) || month < 1 || month > 12)) {
    errors.openingMonths = 'errors.months'
  }
  const delay = values.confirmationDelayHours.trim()
  if (delay) {
    const hours = wholeNumber(delay)
    if (hours === undefined || hours > DELAY_MAX) errors.confirmationDelayHours = 'errors.delayInvalid'
  }
  return errors
}

/** Why each field of the partner would be refused. Empty when it can be sent. */
export function partnerFormErrors(values: PartnerFormValues): PartnerFormErrors {
  const errors: PartnerFormErrors = {}
  const name = text(values.name, TEXT_MAX, 'errors.textTooLong')
  if (name) errors.name = name
  const country = text(values.country, PLACE_MAX, 'errors.placeTooLong')
  if (country) errors.country = country
  const city = text(values.city, PLACE_MAX, 'errors.placeTooLong')
  if (city) errors.city = city
  const email = values.contactEmail.trim()
  if (!email) errors.contactEmail = 'errors.required'
  else if (length(email) > TEXT_MAX) errors.contactEmail = 'errors.textTooLong'
  else if (!EMAIL.test(email)) errors.contactEmail = 'errors.email'
  if (length(values.contactPhone.trim()) > PHONE_MAX) errors.contactPhone = 'errors.phoneTooLong'
  return errors
}

export type CreateOfferBody = {
  partner_id: string
  kind: CatalogKind
  title: string
  description: string
  country: string
  city: string
  min_persons: number
  max_persons: number
  available_from: string
  available_to: string
  tags: string[]
  featured: boolean
  active: boolean
  price_eur: number | null
  price_unit: PriceUnit | null
  opening_months: number[]
  conditions: string | null
  restrictions: string | null
  cancellation: string | null
  confirmation_delay_hours: number | null
}

/** A checked offer, as POST /admin/offers takes it. Empty texts and numbers are null. */
export function toCreateOfferBody(partnerId: string, values: OfferFormValues): CreateOfferBody {
  const delay = values.confirmationDelayHours.trim()
  return {
    partner_id: partnerId,
    ...offerFields(values),
    conditions: values.conditions.trim() || null,
    restrictions: values.restrictions.trim() || null,
    cancellation: values.cancellation.trim() || null,
    confirmation_delay_hours: delay ? Number(delay) : null,
  }
}

export type PatchOfferBody = Omit<CreateOfferBody, 'partner_id' | 'conditions' | 'restrictions' | 'cancellation' | 'confirmation_delay_hours'> & {
  hidden: boolean
  conditions: string
  restrictions: string
  cancellation: string
  confirmation_delay_hours?: number
}

/**
 * Every field of a hand-made offer, as PATCH /admin/offers/{id} takes it: null clears the
 * price with its unit, [] the months and "" a text. The API cannot clear the delay: an empty
 * one is left out.
 */
export function toPatchOfferBody(values: OfferFormValues): PatchOfferBody {
  const delay = values.confirmationDelayHours.trim()
  return {
    ...offerFields(values),
    hidden: values.hidden,
    conditions: values.conditions.trim(),
    restrictions: values.restrictions.trim(),
    cancellation: values.cancellation.trim(),
    ...(delay ? { confirmation_delay_hours: Number(delay) } : {}),
  }
}

export type CreatePartnerBody = {
  name: string
  kind: CatalogKind
  country: string
  city: string
  contact_email: string
  contact_phone?: string
  active: boolean
}

/** A checked partner, as POST /admin/partners takes it. A blank phone is left out. */
export function toCreatePartnerBody(values: PartnerFormValues): CreatePartnerBody {
  const phone = values.contactPhone.trim()
  return {
    name: values.name.trim(),
    kind: values.kind,
    country: values.country.trim(),
    city: values.city.trim(),
    contact_email: values.contactEmail.trim(),
    ...(phone ? { contact_phone: phone } : {}),
    active: values.active,
  }
}

/** Every field of a hand-made partner. The API cannot clear the phone: a blank one is left out. */
export function toPatchPartnerBody(values: PartnerFormValues): CreatePartnerBody & { hidden: boolean } {
  return { ...toCreatePartnerBody(values), hidden: values.hidden }
}

export type PartnerSource = 'all' | 'imported' | 'manual'

/** The partners whose name, city or country holds the search (accents and case aside), from one source. */
export function filterPartners<T extends { name: string; city: string; country: string; imported: boolean }>(
  partners: T[],
  search: string,
  source: PartnerSource,
): T[] {
  const query = fold(search.trim())
  return partners.filter(
    (partner) =>
      (source === 'all' || partner.imported === (source === 'imported')) &&
      (!query || [partner.name, partner.city, partner.country].some((value) => fold(value).includes(query))),
  )
}

export type CatalogRequestErrorKey = 'errors.importedRow' | 'errors.invalid' | 'errors.notFound' | 'errors.unknown'

/** The message key of a refused save, from the API's status and code. */
export function catalogErrorKey(status: number | undefined, code: string | undefined): CatalogRequestErrorKey {
  if (status === 409 && code === 'imported_row') return 'errors.importedRow'
  if (status === 422) return 'errors.invalid'
  if (status === 404) return 'errors.notFound'
  return 'errors.unknown'
}

/** The form's values for an offer read from the API. */
export function offerFormValues(offer: {
  kind: CatalogKind
  title: string
  description: string
  country: string
  city: string
  min_persons: number
  max_persons: number
  available_from: string
  available_to: string
  tags: string[]
  featured: boolean
  active: boolean
  hidden: boolean
  price_eur: number | null
  price_unit: PriceUnit | null
  opening_months: number[]
  conditions: string | null
  restrictions: string | null
  cancellation: string | null
  confirmation_delay_hours: number | null
}): OfferFormValues {
  return {
    kind: offer.kind,
    title: offer.title,
    description: offer.description,
    country: offer.country,
    city: offer.city,
    minPersons: String(offer.min_persons),
    maxPersons: String(offer.max_persons),
    availableFrom: offer.available_from,
    availableTo: offer.available_to,
    tags: offer.tags.join(', '),
    featured: offer.featured,
    active: offer.active,
    hidden: offer.hidden,
    price: offer.price_eur === null ? '' : String(offer.price_eur),
    priceUnit: offer.price_unit ?? '',
    openingMonths: [...offer.opening_months],
    conditions: offer.conditions ?? '',
    restrictions: offer.restrictions ?? '',
    cancellation: offer.cancellation ?? '',
    confirmationDelayHours: offer.confirmation_delay_hours === null ? '' : String(offer.confirmation_delay_hours),
  }
}

/** A new offer of this partner: its kind and place, one person, nothing else. */
export function newOfferFormValues(partner: { kind: CatalogKind; country: string; city: string }): OfferFormValues {
  return {
    kind: partner.kind,
    title: '',
    description: '',
    country: partner.country,
    city: partner.city,
    minPersons: '1',
    maxPersons: '1',
    availableFrom: '',
    availableTo: '',
    tags: '',
    featured: false,
    active: true,
    hidden: false,
    price: '',
    priceUnit: '',
    openingMonths: [],
    conditions: '',
    restrictions: '',
    cancellation: '',
    confirmationDelayHours: '',
  }
}

/** The form's values for a partner read from the API. */
export function partnerFormValues(partner: {
  name: string
  kind: CatalogKind
  country: string
  city: string
  contact_email: string
  contact_phone: string | null
  active: boolean
  hidden: boolean
}): PartnerFormValues {
  return {
    name: partner.name,
    kind: partner.kind,
    country: partner.country,
    city: partner.city,
    contactEmail: partner.contact_email,
    contactPhone: partner.contact_phone ?? '',
    active: partner.active,
    hidden: partner.hidden,
  }
}

export const NEW_PARTNER: PartnerFormValues = {
  name: '',
  kind: 'hotel',
  country: '',
  city: '',
  contactEmail: '',
  contactPhone: '',
  active: true,
  hidden: false,
}

function offerFields(values: OfferFormValues) {
  const price = values.price.trim()
  return {
    kind: values.kind,
    title: values.title.trim(),
    description: values.description.trim(),
    country: values.country.trim(),
    city: values.city.trim(),
    min_persons: Number(values.minPersons.trim()),
    max_persons: Number(values.maxPersons.trim()),
    available_from: values.availableFrom,
    available_to: values.availableTo,
    tags: parseTags(values.tags).tags,
    featured: values.featured,
    active: values.active,
    price_eur: price ? Number(price) : null,
    price_unit: price && values.priceUnit ? values.priceUnit : null,
    opening_months: [...new Set(values.openingMonths)].sort((a, b) => a - b),
  }
}

function text(value: string, max: number, tooLong: CatalogErrorKey): CatalogErrorKey | undefined {
  const trimmed = value.trim()
  if (!trimmed) return 'errors.required'
  return length(trimmed) > max ? tooLong : undefined
}

/** Characters as the API (Pydantic) counts them: code points, so an emoji is one. */
function length(value: string): number {
  return [...value].length
}

function wholeNumber(value: string): number | undefined {
  const trimmed = value.trim()
  return WHOLE.test(trimmed) ? Number(trimmed) : undefined
}

function fold(value: string): string {
  return value.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
}
