export type CatalogKind = 'hotel' | 'guide' | 'transport' | 'activity' | 'agency'
export type PriceUnit = 'person/night' | 'person/trip' | 'person/activity'

/** The kinds of partner and offer, in the order the forms list them. Names: `admin` kinds.<kind>. */
export const KINDS: CatalogKind[] = ['hotel', 'guide', 'transport', 'activity', 'agency']

/** The price units, as the API names them. Names: `admin` units.<unit>. */
export const PRICE_UNITS: PriceUnit[] = ['person/night', 'person/trip', 'person/activity']

export const MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
