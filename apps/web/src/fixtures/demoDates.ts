// Demo dates count from the day the app runs, so the demo trips always look upcoming and recently updated.
import { localIsoDate } from '../lib/dates'

/** The day `days` days after `today` (before it when negative), as YYYY-MM-DD. */
export function daysFromToday(days: number, today = new Date()): string {
  return localIsoDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() + days))
}

/** A moment `days` days before `today` at the local `hour`:`minute`, as an ISO date and time. */
export function timeDaysAgo(days: number, hour: number, minute: number, today = new Date()): string {
  return new Date(today.getFullYear(), today.getMonth(), today.getDate() - days, hour, minute).toISOString()
}

/** The first day of the month of an ISO day: a trip that only has its month so far. */
export function monthOf(iso: string): string {
  return `${iso.slice(0, 7)}-01`
}

/** The first day of the month `months` months after this one, as YYYY-MM-DD. */
export function monthFromToday(months: number, today = new Date()): string {
  return localIsoDate(new Date(today.getFullYear(), today.getMonth() + months, 1))
}
