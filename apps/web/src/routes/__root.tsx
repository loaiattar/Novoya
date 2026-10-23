import type { QueryClient } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import {
  createRootRouteWithContext,
  Outlet,
  useRouter,
  useRouterState,
} from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { serverErrorKey } from '../api/errors'
import { ErrorNote } from '../components/molecules/ErrorNote'
import { HomeLink } from '../components/molecules/HomeLink'
import { resolveLocale } from '../domain/i18n/locale'
import i18n from '../i18n'
import { readStoredLocale } from '../i18n/storedLocale'

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootLayout,
})

// Public pages (landing, login) draw their own header; signed-in pages get theirs from /_authenticated.
function RootLayout() {
  // The user loaded by the /_authenticated guard. Pages outside it, like /login, have none.
  const me = useRouterState({
    select: (state) => state.matches.find((match) => match.routeId === '/_authenticated')?.context.me,
  })

  // The signed-in user's locale wins; signed out (e.g. on /login), the language chosen with
  // the switch on this browser, else the browser's language.
  // The /_authenticated guard already switches before a signed-in page renders; this keeps
  // the language right when there is no user any more, for example after signing out.
  const locale = resolveLocale(me?.locale, navigator.languages, readStoredLocale())
  useEffect(() => {
    if (i18n.language !== locale) void i18n.changeLanguage(locale)
  }, [locale])

  return (
    <>
      <Outlet />
      {import.meta.env.DEV && (
        <>
          <TanStackRouterDevtools position="bottom-right" />
          <ReactQueryDevtools buttonPosition="bottom-left" />
        </>
      )}
    </>
  )
}

/** The page shown when a route fails for another reason than a missing session. */
export function RouteError({ error }: { error?: unknown }) {
  const router = useRouter()
  const { t } = useTranslation('errors')
  // Inside the signed-in layout, its header is already on screen. Otherwise (the session
  // check itself failed, or a public page) draw one, so there is still a way home.
  const layoutHeader = useRouterState({
    select: (state) =>
      state.matches.some((match) => match.routeId === '/_authenticated' && match.status === 'success'),
  })
  return (
    <>
      {!layoutHeader && (
        <header className="flex h-18 items-center border-b border-line px-5 md:h-22 md:px-[5vw]">
          <HomeLink />
        </header>
      )}
      <main className={layoutHeader ? 'pt-26 md:pt-30' : 'pt-8'}>
        <ErrorNote message={t(serverErrorKey(error))} onRetry={() => router.invalidate()} />
      </main>
    </>
  )
}
