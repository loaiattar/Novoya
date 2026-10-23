import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { getMeOptions } from '../../api/generated/@tanstack/react-query.gen'
import { isLocale, type Locale } from '../../domain/i18n/locale'
import { storeLocale } from '../../i18n/storedLocale'
import { useUpdateMe, useUpdateMeBusy } from './useUpdateMe'

/**
 * What the language switch needs. Signed in, the choice is saved on the account
 * (PATCH /me) before the interface switches, so emails and quotes follow it too.
 * Signed out, the interface switches at once. Either way, this browser remembers it.
 */
export function useLanguageChoice() {
  const { i18n } = useTranslation()
  // Only read from the cache, never fetched here: the signed-in guard and the landing load
  // /me already, and asking again would undo the guard's rule on when to check the session.
  const me = useQuery({ ...getMeOptions(), enabled: false })
  const save = useUpdateMe()
  // Also while the personal information form saves.
  const busy = useUpdateMeBusy()

  const language: Locale = isLocale(i18n.language) ? i18n.language : 'en'

  function choose(locale: Locale) {
    if (locale === language || busy) return
    if (me.data) {
      save.mutate({ body: { locale } })
      return
    }
    storeLocale(locale)
    void i18n.changeLanguage(locale)
  }

  return { language, choose, saving: busy, failed: save.isError }
}
