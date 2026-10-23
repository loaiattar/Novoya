import { describe, expect, it } from 'vitest'

import { formatAgencyDay, formatDay, formatDayRange, formatEuros, formatHoursAgo, formatMonth, formatMonthName } from './format'

// Intl puts narrow no-break spaces in some languages: compare with plain spaces.
const plain = (text: string) => text.replace(/[\u00a0\u2009\u202f]/g, ' ')

describe('format', () => {
  it('writes a day in each language, without shifting it by the time zone', () => {
    expect(formatDay('en', '2026-05-12')).toBe('May 12, 2026')
    expect(formatDay('fr', '2026-05-12')).toBe('12 mai 2026')
    expect(formatDay('fr', '2026-05-12', false)).toBe('12 mai')
  })

  it('writes a range of days', () => {
    expect(plain(formatDayRange('fr', '2026-05-12', '2026-05-19'))).toBe('12–19 mai 2026')
    expect(plain(formatDayRange('en', '2026-05-12', '2026-05-19'))).toBe('May 12 – 19, 2026')
  })

  it('writes a month', () => {
    expect(formatMonth('fr', '2026-06-01')).toBe('juin 2026')
  })

  it('names a month by its number', () => {
    expect(formatMonthName('en', 5)).toBe('May')
    expect(formatMonthName('fr', 9)).toBe('septembre')
    expect(formatMonthName('en', 12)).toBe('December')
  })

  it('writes whole euros', () => {
    expect(plain(formatEuros('fr', 1860))).toBe('1 860 €')
    expect(formatEuros('en', 1860)).toBe('€1,860')
  })

  it('shows cents only when a price has some', () => {
    expect(formatEuros('en', 1234.5)).toBe('€1,234.50')
    expect(plain(formatEuros('fr', 1234.5))).toBe('1 234,50 €')
  })

  it('writes the agency day in Paris, whatever the browser zone', () => {
    // 23:30 UTC on 28 October is already 29 October in Paris (UTC+1 in winter).
    expect(formatAgencyDay('en', '2026-10-28T23:30:00Z')).toBe('October 29, 2026')
    expect(formatAgencyDay('fr', '2026-10-28T23:30:00Z')).toBe('29 octobre 2026')
  })

  it('writes a time in the past', () => {
    expect(formatHoursAgo('fr', 2)).toBe('il y a 2 heures')
    expect(formatHoursAgo('en', 1)).toBe('1 hour ago')
  })
})
