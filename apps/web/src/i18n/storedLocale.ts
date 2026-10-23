import { isLocale, type Locale } from '../domain/i18n/locale'

const KEY = 'novoya.locale'

// The language picked with the switch, kept on this browser for the visits signed out.
// localStorage can be missing or throw (private mode, blocked site data): then the choice
// simply lasts until the page is reloaded.

export function readStoredLocale(): Locale | undefined {
  try {
    const value = localStorage.getItem(KEY)
    return isLocale(value) ? value : undefined
  } catch {
    return undefined
  }
}

export function storeLocale(locale: Locale): void {
  try {
    localStorage.setItem(KEY, locale)
  } catch {
    // Not remembered: see above.
  }
}
