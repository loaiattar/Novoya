import { useIsMutating, useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { getMeQueryKey, updateMeMutation } from '../../api/generated/@tanstack/react-query.gen'
import { storeLocale } from '../../i18n/storedLocale'

// One key for every PATCH /me on the page, so the callers can wait for each other.
const UPDATE_ME_KEY = ['updateMe'] as const

/**
 * PATCH /me, and what follows a save: the interface switches to the saved language, this
 * browser remembers it, and everything that shows the user (/me, the signed-in layout) is
 * read again. The language switch and the personal information form both save with it.
 * They never overlap (see useUpdateMeBusy): a late answer would switch the interface to
 * an older language than the one stored.
 */
export function useUpdateMe() {
  const { i18n } = useTranslation()
  const queryClient = useQueryClient()
  const router = useRouter()
  return useMutation({
    ...updateMeMutation(),
    mutationKey: UPDATE_ME_KEY,
    onSuccess: async (user) => {
      storeLocale(user.locale)
      queryClient.setQueryData(getMeQueryKey(), user)
      await i18n.changeLanguage(user.locale)
      await queryClient.invalidateQueries({ queryKey: getMeQueryKey() })
      // The signed-in layout keeps the user it loaded in the route context: reload it.
      await router.invalidate()
    },
  })
}

/** True while any PATCH /me of the page is on its way: the other callers wait for it. */
export function useUpdateMeBusy() {
  return useIsMutating({ mutationKey: UPDATE_ME_KEY }) > 0
}
