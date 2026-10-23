import { useForm } from '@tanstack/react-form'
import { useTranslation } from 'react-i18next'

import { Button } from '../atoms/Button'
import { TextField } from '../molecules/TextField'

type Props = {
  submitLabel: string
  pendingLabel: string
  onSubmit: (email: string) => void
  pending?: boolean
  /** Why the last attempt failed. */
  error?: string
}

/** One e-mail field and a button, to get a link by e-mail: a new password, a new confirmation. */
export function EmailForm({ submitLabel, pendingLabel, onSubmit, pending = false, error }: Props) {
  const { t } = useTranslation('auth')
  const form = useForm({
    defaultValues: { email: '' },
    onSubmit: ({ value }) => {
      if (!pending) onSubmit(value.email.trim())
    },
  })

  return (
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
            error={error}
          />
        )}
      </form.Field>
      <Button type="submit" size="lg" className="mt-2 w-full" disabled={pending}>
        {pending ? pendingLabel : submitLabel}
      </Button>
    </form>
  )
}
