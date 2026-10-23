/** What the client typed in the panel's last step, as the form holds it. */
export type ConstraintsInput = {
  budget: string
  persons: number
  startDate: string
  endDate: string
}

// Texts in errors.json under answers.<key>; the page passes { min, max } for answers.persons.
export type ConstraintsErrorKey =
  | 'answers.budget'
  | 'answers.persons'
  | 'answers.startDate'
  | 'answers.startInPast'
  | 'answers.endDate'
  | 'answers.endBeforeStart'
  | 'answers.tripTooLong'

export type ConstraintsErrors = Partial<Record<keyof ConstraintsInput, ConstraintsErrorKey>>

export const MIN_PERSONS = 1
export const MAX_PERSONS = 50 // AnswerPanelRequest.persons
export const MAX_TRIP_DAYS = 366 // MAX_TRIP_DAYS in the API's answers.py

const DAY_MS = 24 * 60 * 60 * 1000

/** The days of a trip between two YYYY-MM-DD dates, the first and the last included. */
function tripDays(start: string, end: string): number {
  return (Date.parse(end) - Date.parse(start)) / DAY_MS + 1
}

/** "3 500 €", "3500,50" or "3500.5" as the decimal string the API takes ("3500.50"), or null. */
export function parseBudget(text: string): string | null {
  const cleaned = text.replace(/[\s  €]/g, '').replace(',', '.')
  if (!/^\d{1,8}(\.\d{1,2})?$/.test(cleaned)) return null
  const value = Number(cleaned)
  return value > 0 ? value.toFixed(2) : null
}

/**
 * The rules for the answers: a budget above 0, 1 to 50 travellers, and the dates rule, the
 * same as in the API's answers.py: the departure is not in the past, the return is after it
 * and the trip lasts 366 days at most, the first and the last day included. `today` is the user's local day (YYYY-MM-DD); the API, on UTC, accepts
 * one day earlier, so every local day is accepted there too.
 */
export function constraintsErrors(input: ConstraintsInput, today: string): ConstraintsErrors {
  const errors: ConstraintsErrors = {}
  if (parseBudget(input.budget) === null) errors.budget = 'answers.budget'
  if (!Number.isInteger(input.persons) || input.persons < MIN_PERSONS || input.persons > MAX_PERSONS) {
    errors.persons = 'answers.persons'
  }
  if (!input.startDate) errors.startDate = 'answers.startDate'
  else if (input.startDate < today) errors.startDate = 'answers.startInPast'
  if (!input.endDate) errors.endDate = 'answers.endDate'
  else if (input.startDate && input.endDate <= input.startDate) {
    errors.endDate = 'answers.endBeforeStart'
  } else if (input.startDate && tripDays(input.startDate, input.endDate) > MAX_TRIP_DAYS) {
    errors.endDate = 'answers.tripTooLong'
  }
  return errors
}
