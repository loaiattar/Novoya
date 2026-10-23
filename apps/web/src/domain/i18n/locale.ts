export type Locale = 'en' | 'fr'

export const LOCALES: readonly Locale[] = ['en', 'fr']

export function isLocale(value: unknown): value is Locale {
  return LOCALES.includes(value as Locale)
}

/**
 * The language of the interface: the signed-in user's locale (from /me), else the language
 * chosen with the switch on this browser, else the browser's first language, else English.
 * The browser rule is the API's Locale.from_hint, which reads the first language of
 * Accept-Language: fr if it starts with "fr", en otherwise.
 */
export function resolveLocale(
  userLocale: Locale | undefined,
  browserLanguages: readonly string[],
  storedLocale?: Locale,
): Locale {
  if (userLocale) return userLocale
  if (storedLocale) return storedLocale
  return browserLanguages[0]?.trim().toLowerCase().startsWith('fr') ? 'fr' : 'en'
}
