// The demo plan of the demo trips (/trips). Real plans are read from GET /plans/{id}. A plan never has a price (#31).
import { daysFromToday, timeDaysAgo } from './demoDates'
import { PHOTOS } from './photos'

// Titles, texts, moods and tags come from the planner (LLM), already in the user's language.
export type PlanDay = {
  number: number
  /** ISO date, e.g. 2026-05-12. */
  date: string
  title: string
  text: string
  mood: string
}

export type Plan = {
  id: string
  version: number
  /** ISO date and time of the last change. */
  updatedAt: string
  place: string
  tagline: string
  startDate: string
  endDate: string
  travellers: number
  tags: string[]
  photo: string
  photoAlt: string
  days: PlanDay[]
}

const DEMO: Plan = {
  id: 'chania',
  version: 2,
  updatedAt: timeDaysAgo(2, 10, 42),
  place: 'Chania',
  tagline: 'au rythme de la mer.',
  startDate: daysFromToday(60),
  endDate: daysFromToday(66),
  travellers: 2,
  tags: ['calme', 'mer', 'cuisine locale'],
  photo: PHOTOS.crete,
  photoAlt: 'Eaux turquoise de Crète',
  days: [
    { number: 1, date: daysFromToday(60), title: 'Arriver, respirer', text: 'Installation face à la mer, temps libre et première soirée douce dans le vieux port.', mood: 'Très doux' },
    { number: 2, date: daysFromToday(61), title: 'La côte au réveil', text: 'Petit-déjeuner au calme, criques de l’ouest et déjeuner tardif les pieds presque dans l’eau.', mood: 'Équilibré' },
    { number: 3, date: daysFromToday(62), title: 'Chania, côté intime', text: 'Marché, ruelles et rencontre avec une guide locale. Soirée libre selon l’envie.', mood: 'Culture' },
    { number: 4, date: daysFromToday(63), title: 'Une journée sans montre', text: 'Plage confidentielle et table de produits crétois. Rien d’autre au programme.', mood: 'Très doux' },
  ],
}

/** The demo plan, by its id. */
export function getPlan(planId: string): Plan | undefined {
  return planId === DEMO.id ? DEMO : undefined
}

export const DEMO_PLAN_ID = DEMO.id
