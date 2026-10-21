import { useTranslation } from 'react-i18next'

import { agencyView, type AgencyView } from '../../domain/agency/agency'

/** Confirmed agency facts in the language of the page. */
export function useAgency(): AgencyView {
  const { i18n } = useTranslation()
  const locale = i18n.language.startsWith('fr') ? 'fr' : 'en'
  return agencyView(locale)
}
