import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link, useRouter } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../api/errors'
import { getMeQueryKey, resetPasswordMutation } from '../../api/generated/@tanstack/react-query.gen'
import { Eyebrow } from '../../components/atoms/Eyebrow'
import { ResetPasswordForm } from '../../components/organisms/ResetPasswordForm'
import { useAccountErrors } from '../-accountErrors'

type ResetPasswordSearch = {
  /** From the link in the reset e-mail. */
  token?: string
}

export const Route = createFileRoute('/_auth/reset-password')({
  validateSearch: (search: Record<string, unknown>): ResetPasswordSearch => ({
    token: typeof search.token === 'string' && search.token ? search.token : undefined,
  }),
  component: ResetPasswordPage,
})

function ResetPasswordPage() {
  const { token } = Route.useSearch()
  const { t } = useTranslation('auth')
  const { t: tErrors } = useTranslation('errors')
  const queryClient = useQueryClient()
  const router = useRouter()
  const reset = useMutation({
    ...resetPasswordMutation(),
    onSuccess: async () => {
      // Every session is closed, this browser's too.
      queryClient.removeQueries({ queryKey: getMeQueryKey() })
      await router.navigate({ to: '/login', search: { notice: 'password_reset' } })
    },
  })
  const errors = useAccountErrors(reset.error)
  const expired = !token || (reset.error instanceof ApiError && reset.error.code === 'invalid_token')

  return (
    <>
      <Eyebrow>{t('reset.eyebrow')}</Eyebrow>
      <h1 className="mb-2.5 text-display-m">{t('reset.title')}</h1>
      {expired ? (
        <>
          <p role="alert" className="mb-6 text-danger">
            {tErrors('account.invalid_token')}
          </p>
          <Link to="/forgot-password" className="underline underline-offset-4">
            {t('reset.requestNewLink')}
          </Link>
        </>
      ) : (
        <>
          <p className="text-muted">{t('reset.intro')}</p>
          <ResetPasswordForm
            onSubmit={(newPassword) => reset.mutate({ body: { token, new_password: newPassword } })}
            pending={reset.isPending}
            errors={errors}
          />
        </>
      )}
    </>
  )
}
