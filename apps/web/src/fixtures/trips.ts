// Demo data until the API exists (issue #76 for plans, #50 for quote requests).
import { daysFromToday, monthFromToday, monthOf, timeDaysAgo } from './demoDates'
import { PHOTOS } from './photos'

/** Where the trip stands: the page translates it. */
export type ThreadStatus = 'offer_sent' | 'preview_proposed' | 'in_discussion' | 'accepted' | 'refused'

/** The trip's dates: a range, a month (dates not set yet), or nothing yet. */
export type ThreadDates = { start: string; end: string } | { month: string } | null

export type Thread = {
  id: string
  photo: string
  status: ThreadStatus
  /** The status that needs the client's attention. */
  highlight?: boolean
  country: string
  dates: ThreadDates
  title: string
  /** The current preview's version, or null for a draft. */
  version: number | null
  /** ISO date and time of the last change. */
  updatedAt: string
  planId?: string
}

const THREADS: Thread[] = [
  { id: 'chania', photo: PHOTOS.crete, status: 'offer_sent', highlight: true, country: 'Grèce', dates: { start: daysFromToday(60), end: daysFromToday(66) }, title: 'Chania, au rythme de la mer', version: 2, updatedAt: timeDaysAgo(2, 10, 42), planId: 'chania' },
  { id: 'marrakech', photo: PHOTOS.marrakech, status: 'preview_proposed', country: 'Maroc', dates: null, title: 'Marrakech, derrière les portes', version: 1, updatedAt: timeDaysAgo(3, 18, 16) },
  { id: 'biarritz', photo: PHOTOS.biarritz, status: 'in_discussion', country: 'France', dates: { month: monthOf(daysFromToday(97)) }, title: 'Biarritz, plein ouest', version: null, updatedAt: timeDaysAgo(2, 9, 30) },
  { id: 'milos', photo: PHOTOS.hero, status: 'accepted', country: 'Grèce', dates: { month: monthFromToday(1) }, title: 'Milos, lumière des Cyclades', version: 3, updatedAt: timeDaysAgo(49, 14, 12) },
  { id: 'essaouira', photo: PHOTOS.marrakech, status: 'refused', country: 'Maroc', dates: { month: '2026-03-01' }, title: 'Essaouira, au gré du vent', version: 2, updatedAt: '2026-03-08T11:05:00Z' },
]

/** The client's trips. Replace with the API call when it exists. */
export function listThreads(): Thread[] {
  return THREADS
}
