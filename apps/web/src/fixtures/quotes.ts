// The demo quote of the demo trips (/trips). Real quotes are read from GET /quotes/{id}.
import { daysFromToday } from './demoDates'

// Line labels are written by the agent. Amounts are whole euros.
export type QuoteLine = { label: string; amount: number }

export type Quote = {
  id: string
  destination: string
  agentName: string
  /** ISO dates. */
  issuedAt: string
  validUntil: string
  startDate: string
  endDate: string
  travellers: number
  lines: QuoteLine[]
  total: number
  budget: number
}

export const DEMO_QUOTE_ID = 'NV-2026-0182'

const DEMO: Quote = {
  id: DEMO_QUOTE_ID,
  destination: 'Chania',
  agentName: 'Léa',
  issuedAt: daysFromToday(-1),
  validUntil: daysFromToday(6),
  startDate: daysFromToday(60),
  endDate: daysFromToday(66),
  travellers: 2,
  lines: [
    { label: 'Hébergement · 6 nuits', amount: 1860 },
    { label: 'Expériences & visites', amount: 420 },
    { label: 'Transferts sur place', amount: 280 },
    { label: 'Accompagnement DÉTOUR', amount: 190 },
  ],
  total: 2750,
  budget: 3500,
}

/** The demo quote, or undefined for any other id. */
export function getQuote(quoteId: string): Quote | undefined {
  return quoteId === DEMO.id ? DEMO : undefined
}
