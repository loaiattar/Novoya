import { describe, expect, it } from 'vitest'

import {
  catalogErrorKey,
  filterPartners,
  offerFormErrors,
  type OfferFormValues,
  parseTags,
  partnerFormErrors,
  type PartnerFormValues,
  toCreateOfferBody,
  toCreatePartnerBody,
  toPatchOfferBody,
  toPatchPartnerBody,
} from './catalog'

const PARTNER_ID = '00000000-0000-4000-8000-000000000101'

const offer: OfferFormValues = {
  kind: 'hotel',
  title: ' Patio room ',
  description: ' Two beds on the patio. ',
  country: 'Morocco',
  city: 'Fès',
  minPersons: '1',
  maxPersons: '3',
  availableFrom: '2027-03-01',
  availableTo: '2027-10-31',
  tags: 'Style:Riad, style:riad\nmood:calm',
  featured: false,
  active: true,
  hidden: false,
  price: '85',
  priceUnit: 'person/night',
  openingMonths: [10, 3, 4],
  conditions: ' Breakfast included. ',
  restrictions: '',
  cancellation: 'Free until 7 days before.',
  confirmationDelayHours: '24',
}

const partner: PartnerFormValues = {
  name: ' Riad Lune ',
  kind: 'hotel',
  country: ' Morocco ',
  city: ' Fès ',
  contactEmail: ' hello@riad-lune.example ',
  contactPhone: ' +212 600 000 000 ',
  active: true,
  hidden: false,
}

describe('parseTags', () => {
  it('lowercases, trims and drops duplicates, in the order typed', () => {
    expect(parseTags(' Style:Riad, style:riad\nmood:calm  food:street-food ')).toEqual({
      tags: ['style:riad', 'mood:calm', 'food:street-food'],
      invalid: [],
    })
  })

  it('reads an empty text as no tag', () => {
    expect(parseTags('  ,\n ')).toEqual({ tags: [], invalid: [] })
  })

  it.each(['riad', 'style:', ':riad', 'style:riad:old', 'style:riad!', 'style_:riad', 'style:-riad', 'stylé:riad'])(
    'puts %j apart as not section:tag',
    (tag) => {
      expect(parseTags(`mood:calm, ${tag}`).invalid).toEqual([tag.toLowerCase()])
    },
  )

  it.each(['style:old_town', 'kind-of:sea-view', 'a1:b2'])('accepts %j', (tag) => {
    expect(parseTags(tag)).toEqual({ tags: [tag], invalid: [] })
  })
})

describe('offerFormErrors', () => {
  it('accepts a valid offer', () => {
    expect(offerFormErrors(offer)).toEqual({})
  })

  it('accepts an offer without price, months, texts or delay', () => {
    const bare: OfferFormValues = {
      ...offer,
      price: '',
      priceUnit: '',
      openingMonths: [],
      conditions: '',
      cancellation: '',
      confirmationDelayHours: '',
      tags: '',
    }
    expect(offerFormErrors(bare)).toEqual({})
  })

  it('needs a title, a description, a country and a city', () => {
    const errors = offerFormErrors({ ...offer, title: ' ', description: '', country: '', city: ' ' })
    expect(errors).toEqual({
      title: 'errors.required',
      description: 'errors.required',
      country: 'errors.required',
      city: 'errors.required',
    })
  })

  it('limits places to 64 characters and the title to 255', () => {
    expect(offerFormErrors({ ...offer, city: 'a'.repeat(64) }).city).toBeUndefined()
    expect(offerFormErrors({ ...offer, city: 'a'.repeat(65) }).city).toBe('errors.placeTooLong')
    expect(offerFormErrors({ ...offer, country: 'a'.repeat(65) }).country).toBe('errors.placeTooLong')
    expect(offerFormErrors({ ...offer, title: 'a'.repeat(255) }).title).toBeUndefined()
    expect(offerFormErrors({ ...offer, title: 'a'.repeat(256) }).title).toBe('errors.textTooLong')
  })

  it('refuses a tag that is not section:tag', () => {
    expect(offerFormErrors({ ...offer, tags: 'mood:calm, riad' }).tags).toBe('errors.tagsInvalid')
  })

  it('accepts 50 tags and refuses 51', () => {
    const tags = (count: number) => Array.from({ length: count }, (_, i) => `style:t${i}`).join(', ')
    expect(offerFormErrors({ ...offer, tags: tags(50) }).tags).toBeUndefined()
    expect(offerFormErrors({ ...offer, tags: tags(51) }).tags).toBe('errors.tagsTooMany')
  })

  it.each(['0', '-1', '1.5', '', 'two'])('refuses %j as the fewest persons', (minPersons) => {
    expect(offerFormErrors({ ...offer, minPersons }).minPersons).toBe('errors.minPersons')
  })

  it('needs the most persons at least the fewest', () => {
    expect(offerFormErrors({ ...offer, minPersons: '3', maxPersons: '3' }).maxPersons).toBeUndefined()
    expect(offerFormErrors({ ...offer, minPersons: '3', maxPersons: '2' }).maxPersons).toBe('errors.maxBelowMin')
  })

  it('needs both dates, the first on or before the last', () => {
    expect(offerFormErrors({ ...offer, availableTo: offer.availableFrom }).availableTo).toBeUndefined()
    expect(offerFormErrors({ ...offer, availableTo: '2027-02-28' }).availableTo).toBe('errors.datesInverted')
    expect(offerFormErrors({ ...offer, availableFrom: '' }).availableFrom).toBe('errors.required')
    expect(offerFormErrors({ ...offer, availableTo: '' }).availableTo).toBe('errors.required')
  })

  it.each(['0', '-5', '12.5', 'abc'])('refuses %j as a price', (price) => {
    expect(offerFormErrors({ ...offer, price }).price).toBe('errors.priceInvalid')
  })

  it('needs the price and its unit together', () => {
    expect(offerFormErrors({ ...offer, priceUnit: '' }).priceUnit).toBe('errors.unitNeeded')
    expect(offerFormErrors({ ...offer, price: '' }).price).toBe('errors.priceNeeded')
  })

  it('refuses a month outside 1 to 12', () => {
    expect(offerFormErrors({ ...offer, openingMonths: [0] }).openingMonths).toBe('errors.months')
    expect(offerFormErrors({ ...offer, openingMonths: [13] }).openingMonths).toBe('errors.months')
    expect(offerFormErrors({ ...offer, openingMonths: [1, 12] }).openingMonths).toBeUndefined()
  })

  it.each(['-1', '2.5', 'soon'])('refuses %j as the confirmation delay', (confirmationDelayHours) => {
    expect(offerFormErrors({ ...offer, confirmationDelayHours }).confirmationDelayHours).toBe('errors.delayInvalid')
  })

  it('accepts a confirmation delay of 0 hours', () => {
    expect(offerFormErrors({ ...offer, confirmationDelayHours: '0' }).confirmationDelayHours).toBeUndefined()
  })
})

describe('partnerFormErrors', () => {
  it('accepts a valid partner, with or without a phone', () => {
    expect(partnerFormErrors(partner)).toEqual({})
    expect(partnerFormErrors({ ...partner, contactPhone: ' ' })).toEqual({})
  })

  it('needs a name, a country, a city and an email', () => {
    expect(partnerFormErrors({ ...partner, name: ' ', country: '', city: '', contactEmail: '' })).toEqual({
      name: 'errors.required',
      country: 'errors.required',
      city: 'errors.required',
      contactEmail: 'errors.required',
    })
  })

  it.each(['riad-lune.example', 'hello@riad', 'hello @riad.example', '@riad.example', 'hello@riad.'])(
    'refuses %j as an email',
    (contactEmail) => {
      expect(partnerFormErrors({ ...partner, contactEmail }).contactEmail).toBe('errors.email')
    },
  )

  it('limits the name and the email to 255, places to 64 and the phone to 32', () => {
    expect(partnerFormErrors({ ...partner, name: 'a'.repeat(256) }).name).toBe('errors.textTooLong')
    expect(partnerFormErrors({ ...partner, contactEmail: `${'a'.repeat(244)}@riad.example` }).contactEmail).toBe(
      'errors.textTooLong',
    )
    expect(partnerFormErrors({ ...partner, city: 'a'.repeat(65) }).city).toBe('errors.placeTooLong')
    expect(partnerFormErrors({ ...partner, contactPhone: '1'.repeat(32) }).contactPhone).toBeUndefined()
    expect(partnerFormErrors({ ...partner, contactPhone: '1'.repeat(33) }).contactPhone).toBe('errors.phoneTooLong')
  })
})

describe('toCreateOfferBody', () => {
  it('sends the trimmed offer with normalized tags, sorted months and the price with its unit', () => {
    expect(toCreateOfferBody(PARTNER_ID, offer)).toEqual({
      partner_id: PARTNER_ID,
      kind: 'hotel',
      title: 'Patio room',
      description: 'Two beds on the patio.',
      country: 'Morocco',
      city: 'Fès',
      min_persons: 1,
      max_persons: 3,
      available_from: '2027-03-01',
      available_to: '2027-10-31',
      tags: ['style:riad', 'mood:calm'],
      featured: false,
      active: true,
      price_eur: 85,
      price_unit: 'person/night',
      opening_months: [3, 4, 10],
      conditions: 'Breakfast included.',
      restrictions: null,
      cancellation: 'Free until 7 days before.',
      confirmation_delay_hours: 24,
    })
  })

  it('sends no price, unit or delay when they are empty', () => {
    const body = toCreateOfferBody(PARTNER_ID, { ...offer, price: '', priceUnit: '', confirmationDelayHours: '' })
    expect([body.price_eur, body.price_unit, body.confirmation_delay_hours]).toEqual([null, null, null])
  })
})

describe('toPatchOfferBody', () => {
  it('sends every field of a hand-made offer', () => {
    expect(toPatchOfferBody(offer)).toEqual({
      kind: 'hotel',
      title: 'Patio room',
      description: 'Two beds on the patio.',
      country: 'Morocco',
      city: 'Fès',
      min_persons: 1,
      max_persons: 3,
      available_from: '2027-03-01',
      available_to: '2027-10-31',
      tags: ['style:riad', 'mood:calm'],
      featured: false,
      active: true,
      hidden: false,
      price_eur: 85,
      price_unit: 'person/night',
      opening_months: [3, 4, 10],
      conditions: 'Breakfast included.',
      restrictions: '',
      cancellation: 'Free until 7 days before.',
      confirmation_delay_hours: 24,
    })
  })

  it('clears the price and its unit together with null', () => {
    const body = toPatchOfferBody({ ...offer, price: '', priceUnit: '' })
    expect([body.price_eur, body.price_unit]).toEqual([null, null])
  })

  it('clears the months with an empty list', () => {
    expect(toPatchOfferBody({ ...offer, openingMonths: [] }).opening_months).toEqual([])
  })

  it('clears blank conditions, restrictions and cancellation with an empty text', () => {
    const body = toPatchOfferBody({ ...offer, conditions: '  ', restrictions: '', cancellation: ' ' })
    expect([body.conditions, body.restrictions, body.cancellation]).toEqual(['', '', ''])
  })

  it('leaves an empty delay out, as the API cannot clear it', () => {
    expect(toPatchOfferBody({ ...offer, confirmationDelayHours: '' })).not.toHaveProperty('confirmation_delay_hours')
  })
})

describe('toCreatePartnerBody', () => {
  it('sends the trimmed partner', () => {
    expect(toCreatePartnerBody(partner)).toEqual({
      name: 'Riad Lune',
      kind: 'hotel',
      country: 'Morocco',
      city: 'Fès',
      contact_email: 'hello@riad-lune.example',
      contact_phone: '+212 600 000 000',
      active: true,
    })
  })

  it('leaves a blank phone out', () => {
    expect(toCreatePartnerBody({ ...partner, contactPhone: ' ' })).not.toHaveProperty('contact_phone')
  })
})

describe('toPatchPartnerBody', () => {
  it('sends every field of a hand-made partner', () => {
    expect(toPatchPartnerBody(partner)).toEqual({
      name: 'Riad Lune',
      kind: 'hotel',
      country: 'Morocco',
      city: 'Fès',
      contact_email: 'hello@riad-lune.example',
      contact_phone: '+212 600 000 000',
      active: true,
      hidden: false,
    })
  })

  it('leaves a blank phone out, as the API cannot clear it', () => {
    expect(toPatchPartnerBody({ ...partner, contactPhone: '' })).not.toHaveProperty('contact_phone')
  })
})

describe('filterPartners', () => {
  const rows = [
    { id: 'p1', name: 'Riad Lune', city: 'Fès', country: 'Morocco', imported: false },
    { id: 'p2', name: 'Maison Écume', city: 'Sète', country: 'France', imported: true },
    { id: 'p3', name: 'Lodge Nord', city: 'Tromsø', country: 'Norway', imported: true },
  ]
  const ids = (list: { id: string }[]) => list.map((row) => row.id)

  it('keeps every partner without a search or a source', () => {
    expect(ids(filterPartners(rows, '', 'all'))).toEqual(['p1', 'p2', 'p3'])
  })

  it.each([
    ['ecume', ['p2']],
    ['FES', ['p1']],
    ['sete', ['p2']],
    ['norway', ['p3']],
    ['  lune ', ['p1']],
    ['nothing', []],
  ])('finds %j by name, city or country, without accents or case', (query, expected) => {
    expect(ids(filterPartners(rows, query, 'all'))).toEqual(expected)
  })

  it('keeps only the imported or only the hand-made partners', () => {
    expect(ids(filterPartners(rows, '', 'imported'))).toEqual(['p2', 'p3'])
    expect(ids(filterPartners(rows, '', 'manual'))).toEqual(['p1'])
    expect(ids(filterPartners(rows, 'sete', 'manual'))).toEqual([])
  })
})

describe('catalogErrorKey', () => {
  it.each([
    [409, 'imported_row', 'errors.importedRow'],
    [422, 'invalid_offer', 'errors.invalid'],
    [422, 'invalid_input', 'errors.invalid'],
    [404, 'partner_not_found', 'errors.notFound'],
    [404, 'offer_not_found', 'errors.notFound'],
    [500, 'unknown', 'errors.unknown'],
    [undefined, undefined, 'errors.unknown'],
  ])('reads %s %s as %s', (status, code, key) => {
    expect(catalogErrorKey(status, code)).toBe(key)
  })
})

describe('lengths, counted like the API', () => {
  // Pydantic counts code points: an emoji is one character, not two UTF-16 units.
  it('counts an emoji as one character', () => {
    expect(offerFormErrors({ ...offer, title: '😀'.repeat(255) }).title).toBeUndefined()
    expect(offerFormErrors({ ...offer, title: '😀'.repeat(256) }).title).toBe('errors.textTooLong')
    expect(offerFormErrors({ ...offer, city: '😀'.repeat(64) }).city).toBeUndefined()
    expect(partnerFormErrors({ ...partner, name: '😀'.repeat(255) }).name).toBeUndefined()
    expect(partnerFormErrors({ ...partner, contactPhone: '😀'.repeat(32) }).contactPhone).toBeUndefined()
    expect(partnerFormErrors({ ...partner, contactPhone: '😀'.repeat(33) }).contactPhone).toBe('errors.phoneTooLong')
    expect(partnerFormErrors({ ...partner, contactEmail: `${'😀'.repeat(242)}@riad.example` }).contactEmail).toBeUndefined()
  })
})

describe('bounds of the offers columns', () => {
  it('accepts a price up to 1,000,000 euros', () => {
    expect(offerFormErrors({ ...offer, price: '1000000' }).price).toBeUndefined()
    expect(offerFormErrors({ ...offer, price: '1000001' }).price).toBe('errors.priceInvalid')
  })

  it('accepts up to 1,000 persons and refuses more', () => {
    expect(offerFormErrors({ ...offer, maxPersons: '1000' }).maxPersons).toBeUndefined()
    expect(offerFormErrors({ ...offer, maxPersons: '1001' }).maxPersons).toBe('errors.personsTooMany')
    expect(offerFormErrors({ ...offer, minPersons: '1001', maxPersons: '1001' }).minPersons).toBe(
      'errors.personsTooMany',
    )
  })

  it('accepts a confirmation delay up to 720 hours', () => {
    expect(offerFormErrors({ ...offer, confirmationDelayHours: '720' }).confirmationDelayHours).toBeUndefined()
    expect(offerFormErrors({ ...offer, confirmationDelayHours: '721' }).confirmationDelayHours).toBe(
      'errors.delayInvalid',
    )
  })
})
