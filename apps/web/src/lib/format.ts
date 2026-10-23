// Dates and amounts in the interface's language. Pass i18n.language as `locale`.
// ISO dates without a time ('2026-05-12') are read as UTC days, so they never shift by a day.

const day = (iso: string) => new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso)
const utc = { timeZone: 'UTC' } as const

/** 12 May 2026 / 12 mai 2026 (`withYear: false`: 12 May). */
export function formatDay(locale: string, iso: string, withYear = true): string {
  return new Intl.DateTimeFormat(locale, { ...utc, day: 'numeric', month: 'long', year: withYear ? 'numeric' : undefined }).format(day(iso))
}

/** 12–19 May 2026 / 12–19 mai 2026. */
export function formatDayRange(locale: string, start: string, end: string): string {
  return new Intl.DateTimeFormat(locale, { ...utc, day: 'numeric', month: 'long', year: 'numeric' }).formatRange(day(start), day(end))
}

/** June 2026 / juin 2026. */
export function formatMonth(locale: string, iso: string): string {
  return new Intl.DateTimeFormat(locale, { ...utc, month: 'long', year: 'numeric' }).format(day(iso))
}

/** May / mai, for a month number 1-12. */
export function formatMonthName(locale: string, month: number): string {
  return new Intl.DateTimeFormat(locale, { ...utc, month: 'long' }).format(Date.UTC(2026, month - 1, 1))
}

/** May, June and July / mai, juin et juillet. */
export function formatList(locale: string, items: string[]): string {
  return new Intl.ListFormat(locale, { style: 'long', type: 'conjunction' }).format(items)
}

/** 19 Oct, 10:42 / 19 oct., 10:42, in the browser's time zone. */
export function formatDateTime(locale: string, iso: string): string {
  return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
}

/** 12 Oct 2025 / 12 oct. 2025. */
export function formatShortDate(locale: string, iso: string): string {
  return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(iso))
}

/** €1,860 / 1 860 €, and €1,234.50 / 1 234,50 € when there are cents (negotiated prices). */
export function formatEuros(locale: string, amount: number): string {
  const digits = Number.isInteger(amount) ? 0 : 2
  return new Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR', minimumFractionDigits: digits, maximumFractionDigits: digits }).format(amount)
}

/** October 29, 2026 / 29 octobre 2026: the day in Paris, the agency's day, as the quote PDF shows it. */
export function formatAgencyDay(locale: string, iso: string): string {
  return new Intl.DateTimeFormat(locale, { timeZone: 'Europe/Paris', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(iso))
}

/** 2 hours ago / il y a 2 heures. */
export function formatHoursAgo(locale: string, hours: number): string {
  return new Intl.RelativeTimeFormat(locale, { numeric: 'auto' }).format(-hours, 'hour')
}
