// Demo data until the API exists (issue #76, GET /plans/{id}). A plan never has a price (#31).
import { PHOTOS } from './photos'

/** When in the day: the page translates it. */
export type Period = 'morning' | 'midday' | 'evening'

// Titles, texts, moods and tags come from the planner (LLM), already in the user's language.
export type Moment = { time: string; period: Period; title: string; text: string }

export type PlanDay = {
  number: number
  /** ISO date, e.g. 2026-05-12. */
  date: string
  title: string
  text: string
  mood: string
  intro: string
  moments: Moment[]
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
  basedOnPreferences: boolean
  photo: string
  photoAlt: string
  days: PlanDay[]
}

const moments: Moment[] = [
  { time: '08:30', period: 'morning', title: 'Petit-déjeuner face à la baie', text: 'Un début de journée tranquille, sans départ précipité.' },
  { time: '11:00', period: 'midday', title: 'Les criques de l’ouest', text: 'Route panoramique et baignade selon la météo.' },
  { time: '19:30', period: 'evening', title: 'Retour au vieux port', text: 'Une table locale choisie selon vos envies du moment.' },
]

const DEMO: Plan = {
  id: 'chania',
  version: 2,
  updatedAt: '2026-10-19T10:42:00Z',
  place: 'Chania',
  tagline: 'au rythme de la mer.',
  startDate: '2026-05-12',
  endDate: '2026-05-19',
  travellers: 2,
  tags: ['calme', 'mer', 'cuisine locale'],
  basedOnPreferences: true,
  photo: PHOTOS.crete,
  photoAlt: 'Eaux turquoise de Crète',
  days: [
    { number: 1, date: '2026-05-12', title: 'Arriver, respirer', text: 'Installation face à la mer, temps libre et première soirée douce dans le vieux port.', mood: 'Très doux', intro: 'Une arrivée sans hâte, pour poser les valises et regarder la mer.', moments },
    { number: 2, date: '2026-05-13', title: 'La côte au réveil', text: 'Petit-déjeuner au calme, criques de l’ouest et déjeuner tardif les pieds presque dans l’eau.', mood: 'Équilibré', intro: 'Une journée lumineuse, pensée pour laisser la mer donner le tempo.', moments },
    { number: 3, date: '2026-05-14', title: 'Chania, côté intime', text: 'Marché, ruelles et rencontre avec une guide locale. Soirée libre selon l’envie.', mood: 'Culture', intro: 'La ville à pied, avec quelqu’un qui la connaît de l’intérieur.', moments },
    { number: 4, date: '2026-05-15', title: 'Une journée sans montre', text: 'Plage confidentielle et table de produits crétois. Rien d’autre au programme.', mood: 'Très doux', intro: 'Rien à prévoir, tout à savourer.', moments },
  ],
}

/** The plan to show. Replace with the API call when GET /plans/{id} exists. */
export function getPlan(planId: string): Plan | undefined {
  return planId === DEMO.id ? DEMO : undefined
}

export const DEMO_PLAN_ID = DEMO.id
