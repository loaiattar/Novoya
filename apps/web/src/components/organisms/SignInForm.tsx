import { useForm } from '@tanstack/react-form'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { Button } from '../atoms/Button'
import { Divider } from '../atoms/Divider'
import { GoogleButton } from '../molecules/GoogleButton'
import { TextField } from '../molecules/TextField'

type Props = {
  /** Where "Continue with Google" goes. */
  googleHref: string
  onSubmit: (credentials: { email: string; password: string }) => void
  pending?: boolean
  /** Why the last attempt failed. */
  error?: string
}

/** Google, or e-mail and password. The page sends the request and says what went wrong. */
export function SignInForm({ googleHref, onSubmit, pending = false, error }: Props) {
  const { t } = useTranslation('auth')
  const form = useForm({
    defaultValues: { email: '', password: '' },
    onSubmit: ({ value }) => {
      if (!pending) onSubmit({ email: value.email.trim(), password: value.password })
    },
  })

  return (
    <>
      <div className="my-5">
        <GoogleButton href={googleHref} />
      </div>
      <Divider label={t('orWithEmail')} />
      <form
        onSubmit={(event) => {
          event.preventDefault()
          void form.handleSubmit()
        }}
      >
        <form.Field name="email">
          {(field) => (
            <TextField
              label={t('email')}
              type="email"
              name={field.name}
              autoComplete="email"
              required
              placeholder={t('emailPlaceholder')}
              value={field.state.value}
              onChange={field.handleChange}
              onBlur={field.handleBlur}
            />
          )}
        </form.Field>
        <form.Field name="password">
          {(field) => (
            <TextField
              label={t('password')}
              type="password"
              name={field.name}
              autoComplete="current-password"
              required
              value={field.state.value}
              onChange={field.handleChange}
              onBlur={field.handleBlur}
            />
          )}
        </form.Field>
        <p className="-mt-1 mb-4 text-right text-sm">
          <Link to="/forgot-password" className="inline-flex min-h-6 items-center underline underline-offset-4">
            {t('forgotPassword')}
          </Link>
        </p>
        {error && (
          <p role="alert" className="mb-4 text-sm text-danger">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" className="mt-2 w-full" disabled={pending}>
          {pending ? t('signingIn') : t('submit')} <span aria-hidden="true">↗</span>
        </Button>
      </form>
      <p className="mt-6 text-center text-sm">
        {t('noAccount')}{' '}
        <Link to="/signup" className="underline underline-offset-4">
          {t('signUpLink')}
        </Link>
      </p>
    </>
  )
}
