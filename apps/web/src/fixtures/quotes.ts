// Demo data until the API exists (issue #54, see the quote and accept or reject it).
import { daysFromToday } from './demoDates'

// Line labels are written by the agent. Amounts are whole euros.
export type QuoteLine = { label: string; amount: number }

export type Quote = {
  id: string
  destination: string
  agentName: string
  validDays: number
  /** ISO date. */
  issuedAt: string
  startDate: string
  endDate: string
  travellers: number
  days: number
  nights: number
  lines: QuoteLine[]
  total: number
  budget: number
}

const DEMO: Quote = {
  id: 'NV-2026-0182',
  destination: 'Chania',
  agentName: 'Léa',
  validDays: 7,
  issuedAt: daysFromToday(-1),
  startDate: daysFromToday(60),
  endDate: daysFromToday(66),
  travellers: 2,
  days: 7,
  nights: 6,
  lines: [
    { label: 'Hébergement · 6 nuits', amount: 1860 },
    { label: 'Expériences & visites', amount: 420 },
    { label: 'Transferts sur place', amount: 280 },
    { label: 'Accompagnement DÉTOUR', amount: 190 },
  ],
  total: 2750,
  budget: 3500,
}

/** The quote to show. Replace with the API call when #54 exists. */
export function getQuote(quoteId: string): Quote | undefined {
  return quoteId === DEMO.id ? DEMO : undefined
}
