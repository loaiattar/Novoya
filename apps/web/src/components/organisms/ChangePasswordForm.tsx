import { useForm } from '@tanstack/react-form'
import { useTranslation } from 'react-i18next'

import { Button } from '../atoms/Button'
import { TextField } from '../molecules/TextField'

type Passwords = { currentPassword: string; newPassword: string }

type Props = {
  /** Resolves once the password is changed: the form then empties. Rejects on failure. */
  onSubmit: (passwords: Passwords) => Promise<unknown>
  pending?: boolean
  /** Why the last attempt failed: next to its field, or for the whole form. */
  errors?: { currentPassword?: string; newPassword?: string; form?: string }
  /** Said once the password is changed. */
  success?: string
}

/** The current password, then the new one. */
export function ChangePasswordForm({ onSubmit, pending = false, errors = {}, success }: Props) {
  const { t } = useTranslation('settings')
  const form = useForm({
    defaultValues: { currentPassword: '', newPassword: '' },
    onSubmit: async ({ value, formApi }) => {
      if (pending) return
      try {
        await onSubmit(value)
        formApi.reset()
      } catch {
        // The page shows why; keep what was typed.
      }
    },
  })

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        void form.handleSubmit()
      }}
    >
      <form.Field name="currentPassword">
        {(field) => (
          <TextField
            label={t('currentPassword')}
            type="password"
            name={field.name}
            autoComplete="current-password"
            required
            value={field.state.value}
            onChange={field.handleChange}
            onBlur={field.handleBlur}
            error={errors.currentPassword}
          />
        )}
      </form.Field>
      <form.Field name="newPassword">
        {(field) => (
          <TextField
            label={t('newPassword')}
            type="password"
            name={field.name}
            autoComplete="new-password"
            required
            hint={t('passwordHint')}
            value={field.state.value}
            onChange={field.handleChange}
            onBlur={field.handleBlur}
            error={errors.newPassword}
          />
        )}
      </form.Field>
      {errors.form && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {errors.form}
        </p>
      )}
      {success && (
        <p role="status" className="mb-4 text-sm">
          {success}
        </p>
      )}
      <Button type="submit" className="mt-2" disabled={pending}>
        {pending ? t('submitting') : t('submit')}
      </Button>
    </form>
  )
}
