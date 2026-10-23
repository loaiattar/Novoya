type Destination = { country: string; city: string | null }

// Our partners' destinations have their own photo; anything else gets the neutral sea one.
const BY_CITY: Record<string, string> = {
  chania: '/images/elounda-sea-view',
  elounda: '/images/elounda-sea-view',
  biarritz: '/images/biarritz-surf',
  marrakech: '/images/marrakech-riad',
}
const BY_COUNTRY: Record<string, string> = {
  greece: '/images/crete-coast',
  grèce: '/images/crete-coast',
  france: '/images/biarritz-surf',
  morocco: '/images/marrakech-riad',
  maroc: '/images/marrakech-riad',
}
export const FALLBACK_PHOTO = '/images/aegean-boat'

const key = (value: string | null) => (value ?? '').trim().toLowerCase()

/** A photo for a destination: its city's, else its country's, else a neutral one. */
export function destinationPhoto(destination: Destination): string {
  return BY_CITY[key(destination.city)] ?? BY_COUNTRY[key(destination.country)] ?? FALLBACK_PHOTO
}

/** "Chania · Greece", or the country alone. */
export function destinationLabel(destination: Destination): string {
  return destination.city ? `${destination.city} · ${destination.country}` : destination.country
}

/** The place to name in a wish started from a suggestion: the city, else the country. */
export function destinationPlace(destination: Destination): string {
  return destination.city ?? destination.country
}
