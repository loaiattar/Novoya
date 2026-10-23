import { useForm } from '@tanstack/react-form'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { Button } from '../atoms/Button'
import { Divider } from '../atoms/Divider'
import { GoogleButton } from '../molecules/GoogleButton'
import { TextField } from '../molecules/TextField'

type Account = { email: string; password: string; first_name: string; last_name: string }

type Props = {
  /** Where "Continue with Google" goes. */
  googleHref: string
  onSubmit: (account: Account) => void
  pending?: boolean
  /** Why the last attempt failed: next to its field, or for the whole form. */
  errors?: {
    firstName?: string
    lastName?: string
    email?: string
    password?: string
    form?: string
  }
}

/** Google, or a new account with a name, an e-mail and a password. */
export function SignUpForm({ googleHref, onSubmit, pending = false, errors = {} }: Props) {
  const { t } = useTranslation('auth')
  const form = useForm({
    defaultValues: { firstName: '', lastName: '', email: '', password: '' },
    onSubmit: ({ value }) => {
      if (!pending) {
        onSubmit({
          first_name: value.firstName.trim(),
          last_name: value.lastName.trim(),
          email: value.email.trim(),
          password: value.password,
        })
      }
    },
  })

  return (
    <>
      <div className="mt-3 mb-2">
        <GoogleButton href={googleHref} />
      </div>
      <Divider label={t('orWithEmail')} />
      <form
        onSubmit={(event) => {
          event.preventDefault()
          void form.handleSubmit()
        }}
      >
        <div className="grid grid-cols-2 gap-x-3">
          <form.Field name="firstName">
            {(field) => (
              <TextField
                label={t('firstName')}
                name={field.name}
                autoComplete="given-name"
                required
                maxLength={100}
                placeholder={t('firstNamePlaceholder')}
                value={field.state.value}
                onChange={field.handleChange}
                onBlur={field.handleBlur}
                error={errors.firstName}
                className="my-2 [&_label]:mb-1"
              />
            )}
          </form.Field>
          <form.Field name="lastName">
            {(field) => (
              <TextField
                label={t('lastName')}
                name={field.name}
                autoComplete="family-name"
                required
                maxLength={100}
                placeholder={t('lastNamePlaceholder')}
                value={field.state.value}
                onChange={field.handleChange}
                onBlur={field.handleBlur}
                error={errors.lastName}
                className="my-2 [&_label]:mb-1"
              />
            )}
          </form.Field>
        </div>
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
              error={errors.email}
              className="my-2 [&_label]:mb-1"
            />
          )}
        </form.Field>
        <form.Field name="password">
          {(field) => (
            <TextField
              label={t('password')}
              type="password"
              name={field.name}
              autoComplete="new-password"
              required
              hint={t('signUp.passwordHint')}
              value={field.state.value}
              onChange={field.handleChange}
              onBlur={field.handleBlur}
              error={errors.password}
              className="my-2 [&_label]:mb-1"
            />
          )}
        </form.Field>
        {errors.form && (
          <p role="alert" className="mb-4 text-sm text-danger">
            {errors.form}
          </p>
        )}
        <Button type="submit" size="lg" className="mt-1 w-full" disabled={pending}>
          {pending ? t('signUp.submitting') : t('signUp.submit')} <span aria-hidden="true">↗</span>
        </Button>
      </form>
      <p className="mt-3 pb-1 text-center text-sm">
        {t('signUp.haveAccount')}{' '}
        <Link to="/login" className="underline underline-offset-4">
          {t('signUp.signInLink')}
        </Link>
      </p>
    </>
  )
}
