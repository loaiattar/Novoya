import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { agencyView } from '../domain/agency/agency'
import { resolveLocale } from '../domain/i18n/locale'
import { readStoredLocale } from './storedLocale'

// One file per language and screen: locales/<language>/<screen>.json (see docs/I18N.md).
// They are all bundled, so a page never shows before its texts. A new or removed file is
// picked up here; declare its namespace in i18next.d.ts for the types.
const files = import.meta.glob<Record<string, unknown>>('./locales/*/*.json', {
  eager: true,
  import: 'default',
})

export const resources: Record<string, Record<string, Record<string, unknown>>> = {}
for (const [path, messages] of Object.entries(files)) {
  const [, language, namespace] = path.match(/^\.\/locales\/([^/]+)\/([^/]+)\.json$/)!
  ;(resources[language] ??= {})[namespace] = messages
}

export const namespaces = Object.keys(resources.en).sort()

// Keep <html lang> in step, for screen readers and the browser's own features.
i18n.on('languageChanged', (language) => document.documentElement.setAttribute('lang', language))

// Until /me answers, the language chosen on this browser, else the browser's language,
// decides; routes/__root.tsx switches to the user's.
void i18n.use(initReactI18next).init({
  resources,
  ns: namespaces,
  defaultNS: 'common',
  lng: resolveLocale(undefined, navigator.languages, readStoredLocale()),
  fallbackLng: 'en',
  supportedLngs: ['en', 'fr'],
  interpolation: {
    escapeValue: false, // React escapes already
    // {{agency}} in any text is the client agency's name, from brand/agency.json.
    defaultVariables: { agency: agencyView('en').tradeName },
  },
  initAsync: false, // the resources are bundled: ready before the first render
  react: { useSuspense: false },
})

export default i18n
