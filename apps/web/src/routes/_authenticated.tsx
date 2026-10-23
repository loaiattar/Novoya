import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Outlet, redirect, useRouter } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { isUnauthenticated } from '../api/errors'
import { getMeOptions, getMeQueryKey, signOutMutation } from '../api/generated/@tanstack/react-query.gen'
import { AppHeader } from '../components/organisms/AppHeader'
import { displayName } from '../domain/auth/session'
import { resolveLocale } from '../domain/i18n/locale'
import { useActivityGap } from '../hooks/ui/useActivityGap'
import i18n from '../i18n'

// After this long without any action on the page, check the session again on the next navigation.
const IDLE_MS = 3 * 60_000

// Every page under this layout needs a session. Without one, go to /login and come back after.
// Any other failure (API down, network, 500) is rethrown so the error page shows it.
export const Route = createFileRoute('/_authenticated')({
  beforeLoad: async ({ context, location }) => {
    try {
      const me = await context.queryClient.ensureQueryData({ ...getMeOptions(), retry: false })
      // Switch before the page renders, so it never shows in the browser's language first.
      const locale = resolveLocale(me.locale, navigator.languages)
      if (i18n.language !== locale) await i18n.changeLanguage(locale)
      return { me }
    } catch (error) {
      if (isUnauthenticated(error)) {
        throw redirect({ to: '/login', search: { redirect: location.href } })
      }
      throw error
    }
  },
  component: SignedInLayout,
})

function SignedInLayout() {
  const { me } = Route.useRouteContext()
  const queryClient = useQueryClient()
  const router = useRouter()
  const { t } = useTranslation('header')
  const signOut = useMutation({
    ...signOutMutation(),
    onSuccess: async () => {
      queryClient.clear()
      await router.navigate({ to: '/login' })
    },
    // On failure the session cookie may still be valid: stay here and say so.
  })

  useActivityGap(IDLE_MS, () => queryClient.removeQueries({ queryKey: getMeQueryKey() }))

  return (
    <>
      <AppHeader
        userName={displayName(me)}
        role={me.role}
        onSignOut={() => signOut.mutate({})}
        signingOut={signOut.isPending}
        signOutError={signOut.isError ? t('signOutFailed') : undefined}
      />
      <Outlet />
    </>
  )
}
