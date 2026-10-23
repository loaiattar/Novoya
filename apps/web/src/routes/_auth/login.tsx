import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, useRouter } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { googleSignInUrl } from '../../api/auth'
import { ApiError } from '../../api/errors'
import { getMeQueryKey, signInWithPasswordMutation } from '../../api/generated/@tanstack/react-query.gen'
import { Eyebrow } from '../../components/atoms/Eyebrow'
import { SignInForm } from '../../components/organisms/SignInForm'
import { passwordSignInErrorKey, signInErrorKey } from '../../domain/auth/errors'
import { safeRedirect } from '../../domain/auth/session'
import { redirectIfSignedIn } from '../-guards'

type LoginSearch = {
  /** The page to go back to after signing in. */
  redirect?: string
  /** Set by the API when a Google sign-in fails. */
  error?: string
  /** Set by the reset password page once the new password is saved. */
  notice?: 'password_reset'
}

export const Route = createFileRoute('/_auth/login')({
  validateSearch: (search: Record<string, unknown>): LoginSearch => ({
    redirect: typeof search.redirect === 'string' ? search.redirect : undefined,
    error: typeof search.error === 'string' ? search.error : undefined,
    notice: search.notice === 'password_reset' ? 'password_reset' : undefined,
  }),
  beforeLoad: ({ context, search }) =>
    redirectIfSignedIn(context.queryClient, safeRedirect(search.redirect, '/wish')),
  component: LoginPage,
})

function LoginPage() {
  const { redirect: target, error, notice } = Route.useSearch()
  const { t } = useTranslation('auth')
  const { t: tErrors } = useTranslation('errors')
  const googleErrorKey = signInErrorKey(error)
  const next = safeRedirect(target, '/wish')
  const queryClient = useQueryClient()
  const router = useRouter()
  const signIn = useMutation({
    ...signInWithPasswordMutation(),
    onSuccess: async () => {
      // The 401 from before is stale: the next page asks /me again with the new session cookie.
      queryClient.removeQueries({ queryKey: getMeQueryKey() })
      await router.navigate({ href: next })
    },
  })
  const passwordError = signIn.isError
    ? tErrors(passwordSignInErrorKey(signIn.error instanceof ApiError ? signIn.error.code : undefined))
    : undefined

  return (
    <>
      <Eyebrow>{t('welcomeBack')}</Eyebrow>
      <h1 className="mb-2.5 text-display-m">{t('title')}</h1>
      <p className="text-muted">{t('intro')}</p>
      {notice === 'password_reset' && (
        <p role="status" className="mt-4 text-sm">
          {t('passwordReset')}
        </p>
      )}
      {googleErrorKey && (
        <p role="alert" className="mt-4 text-sm text-danger">
          {tErrors(googleErrorKey)}
        </p>
      )}
      <SignInForm
        googleHref={googleSignInUrl(next)}
        onSubmit={(body) => signIn.mutate({ body })}
        pending={signIn.isPending}
        error={passwordError}
      />
    </>
  )
}
