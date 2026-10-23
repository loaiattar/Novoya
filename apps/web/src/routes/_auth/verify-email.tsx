import { useMutation, useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { ApiError, serverErrorKey } from '../../api/errors'
import { resendVerificationEmailMutation } from '../../api/generated/@tanstack/react-query.gen'
import { verifyEmail } from '../../api/generated/sdk.gen'
import { Button } from '../../components/atoms/Button'
import { Eyebrow } from '../../components/atoms/Eyebrow'
import { ErrorNote } from '../../components/molecules/ErrorNote'
import { EmailForm } from '../../components/organisms/EmailForm'
import { useAccountErrors } from '../-accountErrors'

type VerifyEmailSearch = {
  /** From the link in the confirmation e-mail. */
  token?: string
}

export const Route = createFileRoute('/_auth/verify-email')({
  validateSearch: (search: Record<string, unknown>): VerifyEmailSearch => ({
    token: typeof search.token === 'string' && search.token ? search.token : undefined,
  }),
  component: VerifyEmailPage,
})

function VerifyEmailPage() {
  const { token } = Route.useSearch()
  const { t } = useTranslation('auth')
  const { t: tErrors } = useTranslation('errors')
  // A query, not a mutation: the token works once, and a query runs once per token even when
  // the page renders twice (StrictMode, a re-render while it is pending).
  const verification = useQuery({
    queryKey: ['verifyEmail', token],
    queryFn: async () => {
      await verifyEmail({ body: { token: token! }, throwOnError: true })
      return true
    },
    enabled: Boolean(token),
    retry: false,
    staleTime: Infinity,
    gcTime: Infinity,
  })
  const resend = useMutation(resendVerificationEmailMutation())
  const resendErrors = useAccountErrors(resend.error)

  const expired =
    !token || (verification.error instanceof ApiError && verification.error.code === 'invalid_token')

  if (expired) {
    return (
      <>
        <Eyebrow>{t('verifyEmail.eyebrow')}</Eyebrow>
        <h1 className="mb-2.5 text-display-m">{t('verifyEmail.expiredTitle')}</h1>
        <p className="mb-2 text-muted">{t('verifyEmail.expiredBody')}</p>
        {resend.isSuccess ? (
          <p role="status" className="mt-4">
            {t('verifyEmail.resent')}
          </p>
        ) : (
          <EmailForm
            submitLabel={t('verifyEmail.resend')}
            pendingLabel={t('verifyEmail.resending')}
            onSubmit={(email) => resend.mutate({ body: { email } })}
            pending={resend.isPending}
            error={resendErrors.email ?? resendErrors.form}
          />
        )}
      </>
    )
  }

  if (verification.isError) {
    return <ErrorNote message={tErrors(serverErrorKey(verification.error))} onRetry={() => void verification.refetch()} />
  }

  if (verification.isPending) {
    return (
      <>
        <Eyebrow>{t('verifyEmail.eyebrow')}</Eyebrow>
        <p role="status" className="text-muted">
          {t('verifyEmail.verifying')}
        </p>
      </>
    )
  }

  return (
    <>
      <Eyebrow>{t('verifyEmail.eyebrow')}</Eyebrow>
      <h1 className="mb-2.5 text-display-m">{t('verifyEmail.doneTitle')}</h1>
      <p role="status" className="mb-6 text-muted">
        {t('verifyEmail.doneBody')}
      </p>
      <Button asChild size="lg" className="w-full">
        <Link to="/login">{t('verifyEmail.signIn')}</Link>
      </Button>
    </>
  )
}
