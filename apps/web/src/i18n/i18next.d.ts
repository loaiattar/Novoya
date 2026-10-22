import 'i18next'

import type admin from './locales/en/admin.json'
import type agent from './locales/en/agent.json'
import type auth from './locales/en/auth.json'
import type building from './locales/en/building.json'
import type common from './locales/en/common.json'
import type demo from './locales/en/demo.json'
import type destinations from './locales/en/destinations.json'
import type errors from './locales/en/errors.json'
import type header from './locales/en/header.json'
import type home from './locales/en/home.json'
import type legal from './locales/en/legal.json'
import type offer from './locales/en/offer.json'
import type plan from './locales/en/plan.json'
import type preferences from './locales/en/preferences.json'
import type privacy from './locales/en/privacy.json'
import type quote from './locales/en/quote.json'
import type settings from './locales/en/settings.json'
import type trips from './locales/en/trips.json'
import type wish from './locales/en/wish.json'

// The English files are the reference: t() only accepts keys that exist in them.
// Add each new namespace (screen) here.
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common'
    resources: {
      admin: typeof admin
      agent: typeof agent
      auth: typeof auth
      building: typeof building
      common: typeof common
      demo: typeof demo
      destinations: typeof destinations
      errors: typeof errors
      header: typeof header
      home: typeof home
      legal: typeof legal
      offer: typeof offer
      plan: typeof plan
      preferences: typeof preferences
      privacy: typeof privacy
      quote: typeof quote
      settings: typeof settings
      trips: typeof trips
      wish: typeof wish
    }
  }
}
