// The admin activity pages: every wish, plan and quote with its status (#130). The statuses
// are the API's, in the order a request goes through them. Pure.

import { formatDay, formatDayRange } from '@/lib/format'

export const WISH_STATUSES = ['draft', 'not_covered', 'panel_shown', 'answered', 'planned'] as const
export const PLAN_STATUSES = ['proposed', 'requested', 'negotiating', 'quoted', 'accepted', 'rejected'] as const
export const QUOTE_STATUSES = ['open', 'expired', 'accepted', 'rejected'] as const

export type WishStatus = (typeof WISH_STATUSES)[number]
export type PlanStatus = (typeof PLAN_STATUSES)[number]
export type QuoteStatus = (typeof QUOTE_STATUSES)[number]

export const ACTIVITY_TABS = ['wishes', 'plans', 'quotes'] as const
export type ActivityTab = (typeof ACTIVITY_TABS)[number]

/** The statuses that wait on the agency: a plan nobody took yet, a quote with no answer in time. */
export function needsAttention(status: string): boolean {
  return status === 'requested' || status === 'expired'
}

/** "Chania, Greece", "Greece" or null when the wish has no destination yet. */
export function placeOf(trip: { city: string | null; country: string | null }): string | null {
  const parts = [trip.city, trip.country].filter(Boolean)
  return parts.length > 0 ? parts.join(', ') : null
}

/** 10–17 May 2026, 10 May 2026, or null when the client has not given dates yet. */
export function datesOf(locale: string, trip: { start_date: string | null; end_date: string | null }): string | null {
  if (trip.start_date && trip.end_date) return formatDayRange(locale, trip.start_date, trip.end_date)
  if (trip.start_date) return formatDay(locale, trip.start_date)
  return null
}
