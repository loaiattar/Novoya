import { describe, expect, it } from 'vitest'

import { datesOf, needsAttention, placeOf } from './activity'

describe('admin activity', () => {
  it('names the place from the city and the country', () => {
    expect(placeOf({ city: 'Chania', country: 'Greece' })).toBe('Chania, Greece')
    expect(placeOf({ city: null, country: 'Greece' })).toBe('Greece')
    expect(placeOf({ city: null, country: null })).toBeNull()
  })

  it('gives the dates in the interface language', () => {
    // ICU may put thin spaces around the dash.
    expect(datesOf('en-GB', { start_date: '2026-05-10', end_date: '2026-05-17' })).toMatch(/^10\s?–\s?17 May 2026$/)
    expect(datesOf('fr', { start_date: '2026-05-10', end_date: null })).toBe('10 mai 2026')
    expect(datesOf('en', { start_date: null, end_date: null })).toBeNull()
  })

  it('flags what waits on the agency', () => {
    expect(needsAttention('requested')).toBe(true)
    expect(needsAttention('expired')).toBe(true)
    expect(needsAttention('negotiating')).toBe(false)
  })
})
