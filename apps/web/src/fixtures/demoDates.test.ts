import { afterAll, describe, expect, it, vi } from 'vitest'

// The fixtures read the date when they are imported: set the clock first, on the last day of a
// month, where "next month" is only a day away and a later day would be in another month.
vi.hoisted(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 31, 23, 30))
})

import { localIsoDate } from '../lib/dates'
import { daysFromToday, monthFromToday, monthOf, timeDaysAgo } from './demoDates'
import { DEMO_PLAN_ID, getPlan } from './plans'
import { getQuote } from './quotes'

afterAll(() => {
  vi.useRealTimers()
})

describe('daysFromToday', () => {
  it('counts days from the given day, across months and years', () => {
    const today = new Date(2026, 11, 30, 23, 30)
    expect(daysFromToday(0, today)).toBe('2026-12-30')
    expect(daysFromToday(3, today)).toBe('2027-01-02')
    expect(daysFromToday(-1, today)).toBe('2026-12-29')
  })
})

describe('monthFromToday', () => {
  it('gives the first day of the month, n months later', () => {
    const today = new Date(2026, 10, 30)
    expect(monthFromToday(1, today)).toBe('2026-12-01')
    expect(monthFromToday(2, today)).toBe('2027-01-01')
  })
})

describe('timeDaysAgo', () => {
  it('gives the local time n days earlier, across a month', () => {
    const today = new Date(2026, 10, 1, 9, 0)
    expect(new Date(timeDaysAgo(2, 10, 42, today))).toEqual(new Date(2026, 9, 30, 10, 42))
  })
})

describe('monthOf', () => {
  it('gives the first day of the month of a day', () => {
    expect(monthOf('2027-02-05')).toBe('2027-02-01')
  })
})

// The demo plan and quote must look upcoming and recent, whatever the day the demo runs.
describe('demo fixtures', () => {
  const today = localIsoDate()
  const plan = getPlan(DEMO_PLAN_ID)!
  const quote = getQuote('NV-2026-0182')!

  it('read the pinned day', () => {
    expect(today).toBe('2026-10-31')
  })

  it('start the Chania plan after today, its days in order from the start', () => {
    expect(plan.startDate > today).toBe(true)
    expect(plan.endDate > plan.startDate).toBe(true)
    plan.days.forEach((day, index) => expect(day.date).toBe(daysAfter(plan.startDate, index)))
  })

  it('give the Chania plan and quote the same dates', () => {
    expect({ startDate: quote.startDate, endDate: quote.endDate }).toEqual({ startDate: plan.startDate, endDate: plan.endDate })
  })

  it('update the Chania plan before the quote is issued', () => {
    expect(localIsoDate(new Date(plan.updatedAt)) < quote.issuedAt).toBe(true)
  })

  it('issue the quote before today, valid a week from then', () => {
    expect(quote.issuedAt < today).toBe(true)
    expect(quote.validUntil).toBe(daysAfter(quote.issuedAt, 7))
    expect(quote.validUntil > today).toBe(true)
  })
})

function daysAfter(iso: string, days: number): string {
  const [year, month, day] = iso.split('-').map(Number)
  return localIsoDate(new Date(year, month - 1, day + days))
}
