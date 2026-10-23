import { useMutation } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { forgotPasswordMutation } from '../../api/generated/@tanstack/react-query.gen'
import { Eyebrow } from '../../components/atoms/Eyebrow'
import { EmailForm } from '../../components/organisms/EmailForm'
import { useAccountErrors } from '../-accountErrors'

export const Route = createFileRoute('/_auth/forgot-password')({
  component: ForgotPasswordPage,
})

function ForgotPasswordPage() {
  const { t } = useTranslation('auth')
  const forgot = useMutation(forgotPasswordMutation())
  const errors = useAccountErrors(forgot.error)

  return (
    <>
      <Eyebrow>{t('forgot.eyebrow')}</Eyebrow>
      {forgot.isSuccess ? (
        <>
          <h1 className="mb-2.5 text-display-m">{t('forgot.sentTitle')}</h1>
          {/* The same answer whether the account exists or not: the API says nothing either. */}
          <p role="status" className="text-muted">
            {t('forgot.sentBody')}
          </p>
        </>
      ) : (
        <>
          <h1 className="mb-2.5 text-display-m">{t('forgot.title')}</h1>
          <p className="text-muted">{t('forgot.intro')}</p>
          <EmailForm
            submitLabel={t('forgot.submit')}
            pendingLabel={t('forgot.submitting')}
            onSubmit={(email) => forgot.mutate({ body: { email } })}
            pending={forgot.isPending}
            error={errors.email ?? errors.form}
          />
        </>
      )}
      <p className="mt-6 text-sm">
        <Link to="/login" className="underline underline-offset-4">
          {t('forgot.backToSignIn')}
        </Link>
      </p>
    </>
  )
}
