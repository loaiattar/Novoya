// The API stores country names in English (ADR 0014). They are shown in the page's language
// through their ISO region code, found once from the English names Intl itself knows.

// English names the catalogue spells differently from Intl ("Bosnia & Herzegovina", "Côte d’Ivoire").
const ALIASES: Record<string, string> = {
  'bosnia and herzegovina': 'BA',
  'ivory coast': 'CI',
}

let codes: Map<string, string> | undefined

function regionCodes(): Map<string, string> {
  if (codes) return codes
  codes = new Map(Object.entries(ALIASES))
  const english = new Intl.DisplayNames(['en'], { type: 'region', fallback: 'none' })
  for (let first = 65; first <= 90; first++) {
    for (let second = 65; second <= 90; second++) {
      const code = String.fromCharCode(first, second)
      const name = english.of(code)?.toLowerCase()
      // ZZ is "Unknown Region"; keep the first code of a name (the aliases win).
      if (name && code !== 'ZZ' && !codes.has(name)) codes.set(name, code)
    }
  }
  return codes
}

/** Greece -> Grèce in French. A name with no known region is shown as given. */
export function localizeCountry(locale: string, englishName: string): string {
  const code = regionCodes().get(englishName.trim().toLowerCase())
  if (!code) return englishName
  return new Intl.DisplayNames([locale], { type: 'region', fallback: 'none' }).of(code) ?? englishName
}
