import { useForm, useStore } from '@tanstack/react-form'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import type { Locale } from '../../domain/i18n/locale'
import { Button } from '../atoms/Button'
import { SelectField } from '../molecules/SelectField'
import { TextField } from '../molecules/TextField'

export type Profile = { firstName: string; lastName: string; locale: Locale }

type Props = {
  /** What is stored now. */
  profile: Profile
  /** Shown, never sent: it is the sign-in identity. */
  email: string
  /** Which names must be filled in. Both by default. */
  required?: { firstName?: boolean; lastName?: boolean }
  /** Resolves with what the API stored, which the form then shows. Rejects on failure. */
  onSubmit: (profile: Profile) => Promise<Profile>
  pending?: boolean
  /** Why the last save failed: next to its field, or for the whole form. */
  errors?: { firstName?: string; lastName?: string; form?: string }
  /** Said once the save worked, until the next edit. */
  success?: string
}

/** The client's first name, last name and language, and their e-mail, read-only. */
export function ProfileForm({
  profile,
  email,
  required = { firstName: true, lastName: true },
  onSubmit,
  pending = false,
  errors = {},
  success,
}: Props) {
  const { t } = useTranslation('profile')
  const form = useForm({
    defaultValues: profile,
    onSubmit: async ({ value, formApi }) => {
      try {
        formApi.reset(await onSubmit(value))
      } catch {
        // The page shows why; keep what was typed.
      }
    },
  })
  const dirty = useStore(form.store, (state) => state.isDirty)
  // Set at once by handleSubmit, unlike `pending`, which needs a render: a double tap
  // sends one request.
  const submitting = useStore(form.store, (state) => state.isSubmitting)

  // What is stored can change elsewhere (the header's language switch): follow it in every
  // field the client has not edited, so a save never sends an old value back.
  const { firstName, lastName, locale } = profile
  useEffect(() => {
    const stored: Profile = { firstName, lastName, locale }
    for (const name of ['firstName', 'lastName', 'locale'] as const) {
      if (!form.getFieldMeta(name)?.isDirty && form.getFieldValue(name) !== stored[name]) {
        form.setFieldValue(name, stored[name], { dontUpdateMeta: true })
      }
    }
  }, [form, firstName, lastName, locale])

  return (
    <form
      aria-label={t('title')}
      className="max-w-[420px]"
      // The API's messages show next to each field, the browser's own bubbles would not.
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        if (pending || form.state.isSubmitting) return
        void form.handleSubmit()
      }}
    >
      <form.Field name="firstName">
        {(field) => (
          <TextField
            label={t('firstName')}
            name={field.name}
            autoComplete="given-name"
            required={required.firstName}
            maxLength={100}
            value={field.state.value}
            onChange={field.handleChange}
            onBlur={field.handleBlur}
            error={errors.firstName}
          />
        )}
      </form.Field>
      <form.Field name="lastName">
        {(field) => (
          <TextField
            label={t('lastName')}
            name={field.name}
            autoComplete="family-name"
            required={required.lastName}
            maxLength={100}
            value={field.state.value}
            onChange={field.handleChange}
            onBlur={field.handleBlur}
            error={errors.lastName}
          />
        )}
      </form.Field>
      <TextField label={t('email')} type="email" value={email} onChange={() => {}} readOnly hint={t('emailHint')} />
      <form.Field name="locale">
        {(field) => (
          <SelectField<Locale>
            label={t('language')}
            value={field.state.value}
            options={[
              { value: 'en', label: 'English' },
              { value: 'fr', label: 'Français' },
            ]}
            onChange={(value) => {
              if (value) field.handleChange(value)
            }}
          />
        )}
      </form.Field>
      {errors.form && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {errors.form}
        </p>
      )}
      {success && !dirty && (
        <p role="status" className="mb-4 text-sm">
          {success}
        </p>
      )}
      <Button type="submit" className="mt-2 w-full sm:w-auto" disabled={pending || submitting}>
        {pending || submitting ? t('saving') : t('save')}
      </Button>
    </form>
  )
}
