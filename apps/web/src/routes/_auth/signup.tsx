import { useMutation } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { googleSignInUrl } from '../../api/auth'
import { registerMutation } from '../../api/generated/@tanstack/react-query.gen'
import { Eyebrow } from '../../components/atoms/Eyebrow'
import { SignUpForm } from '../../components/organisms/SignUpForm'
import { useAccountErrors } from '../-accountErrors'
import { redirectIfSignedIn } from '../-guards'

export const Route = createFileRoute('/_auth/signup')({
  beforeLoad: ({ context }) => redirectIfSignedIn(context.queryClient, '/wish'),
  component: SignUpPage,
})

function SignUpPage() {
  const { t, i18n } = useTranslation('auth')
  const register = useMutation(registerMutation())
  const errors = useAccountErrors(register.error)

  if (register.isSuccess) {
    return (
      <>
        <Eyebrow>{t('signUp.eyebrow')}</Eyebrow>
        <h1 className="mb-2.5 text-display-m">{t('signUp.checkTitle')}</h1>
        <p role="status" className="text-muted">
          {t('signUp.checkBody', { email: register.data.email })}
        </p>
        <p className="mt-6 text-sm">
          <Link to="/login" className="underline underline-offset-4">
            {t('forgot.backToSignIn')}
          </Link>
        </p>
      </>
    )
  }

  return (
    <>
      <Eyebrow className="mb-2">{t('signUp.eyebrow')}</Eyebrow>
      <h1 className="mb-1.5 text-display-s">{t('signUp.title')}</h1>
      <p className="text-sm text-muted">{t('signUp.intro')}</p>
      <SignUpForm
        googleHref={googleSignInUrl('/wish')}
        onSubmit={(account) =>
          register.mutate({ body: { ...account, locale: i18n.language === 'fr' ? 'fr' : 'en' } })
        }
        pending={register.isPending}
        errors={errors}
      />
    </>
  )
}
