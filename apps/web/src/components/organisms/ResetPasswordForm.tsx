import { useForm } from '@tanstack/react-form'
import { useTranslation } from 'react-i18next'

import { Button } from '../atoms/Button'
import { TextField } from '../molecules/TextField'

type Props = {
  onSubmit: (newPassword: string) => void
  pending?: boolean
  /** Why the last attempt failed: next to the field, or for the whole form. */
  errors?: { password?: string; form?: string }
}

/** The new password, chosen from the link of a reset e-mail. */
export function ResetPasswordForm({ onSubmit, pending = false, errors = {} }: Props) {
  const { t } = useTranslation('auth')
  const form = useForm({
    defaultValues: { password: '' },
    onSubmit: ({ value }) => {
      if (!pending) onSubmit(value.password)
    },
  })

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        void form.handleSubmit()
      }}
    >
      <form.Field name="password">
        {(field) => (
          <TextField
            label={t('reset.newPassword')}
            type="password"
            name={field.name}
            autoComplete="new-password"
            required
            hint={t('signUp.passwordHint')}
            value={field.state.value}
            onChange={field.handleChange}
            onBlur={field.handleBlur}
            error={errors.password}
          />
        )}
      </form.Field>
      {errors.form && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {errors.form}
        </p>
      )}
      <Button type="submit" size="lg" className="mt-2 w-full" disabled={pending}>
        {pending ? t('reset.submitting') : t('reset.submit')}
      </Button>
    </form>
  )
}
