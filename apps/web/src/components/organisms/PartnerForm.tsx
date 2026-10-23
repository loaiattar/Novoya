import { useForm } from '@tanstack/react-form'
import { useTranslation } from 'react-i18next'

import { Button } from '../atoms/Button'
import { CheckField } from '../molecules/CheckField'
import { SelectField } from '../molecules/SelectField'
import { TextField } from '../molecules/TextField'
import { type CatalogKind, KINDS } from './catalog'

export type PartnerFields = {
  name: string
  kind: CatalogKind
  country: string
  city: string
  contactEmail: string
  contactPhone: string
  active: boolean
  hidden: boolean
}

type Props = {
  initialValues: PartnerFields
  /** create: a new partner (it starts shown); edit: an existing one, which can be hidden. */
  mode: 'create' | 'edit'
  /** It comes from the agency's own system: only hidden can change here. */
  imported?: boolean
  /** Resolves once saved. Rejects when the values are refused: they stay as typed. */
  onSubmit: (values: PartnerFields) => Promise<unknown>
  pending?: boolean
  /** Why the last attempt failed: next to its field, or for the whole form. */
  errors?: Partial<Record<keyof PartnerFields | 'form', string>>
  /** Said once saved. */
  success?: string
}

/** A partner: name, kind, place and contact, then whether it is active and shown. */
export function PartnerForm({ initialValues, mode, imported = false, onSubmit, pending = false, errors = {}, success }: Props) {
  const { t } = useTranslation('admin')
  const form = useForm({
    defaultValues: initialValues,
    onSubmit: async ({ value }) => {
      if (pending) return
      try {
        await onSubmit(value)
      } catch {
        // The page shows why; keep what was typed.
      }
    },
  })
  const locked = imported

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        void form.handleSubmit()
      }}
      className="max-w-2xl"
    >
      {imported && <p className="mb-4 border-s-2 border-coral bg-ivory p-4 text-sm">{t('partners.form.importedNote')}</p>}
      <form.Field name="name">
        {(field) => (
          <TextField
            label={t('partners.form.name')}
            name={field.name}
            value={field.state.value}
            onChange={field.handleChange}
            onBlur={field.handleBlur}
            readOnly={locked}
            error={errors.name}
          />
        )}
      </form.Field>
      <form.Field name="kind">
        {(field) => (
          <SelectField<CatalogKind>
            label={t('partners.form.kind')}
            value={field.state.value}
            options={KINDS.map((kind) => ({ value: kind, label: t(`kinds.${kind}`) }))}
            onChange={(kind) => kind && field.handleChange(kind)}
            disabled={locked}
            error={errors.kind}
          />
        )}
      </form.Field>
      <div className="md:grid md:grid-cols-2 md:gap-x-5">
        <form.Field name="country">
          {(field) => (
            <TextField
              label={t('partners.form.country')}
              name={field.name}
              value={field.state.value}
              onChange={field.handleChange}
              onBlur={field.handleBlur}
              readOnly={locked}
              error={errors.country}
            />
          )}
        </form.Field>
        <form.Field name="city">
          {(field) => (
            <TextField
              label={t('partners.form.city')}
              name={field.name}
              value={field.state.value}
              onChange={field.handleChange}
              onBlur={field.handleBlur}
              readOnly={locked}
              error={errors.city}
            />
          )}
        </form.Field>
        <form.Field name="contactEmail">
          {(field) => (
            <TextField
              label={t('partners.form.contactEmail')}
              type="email"
              name={field.name}
              autoComplete="off"
              value={field.state.value}
              onChange={field.handleChange}
              onBlur={field.handleBlur}
              readOnly={locked}
              error={errors.contactEmail}
            />
          )}
        </form.Field>
        <form.Field name="contactPhone">
          {(field) => (
            <TextField
              label={t('partners.form.contactPhone')}
              type="tel"
              name={field.name}
              autoComplete="off"
              hint={mode === 'edit' && !locked ? t('partners.form.phoneHint') : undefined}
              value={field.state.value}
              onChange={field.handleChange}
              onBlur={field.handleBlur}
              readOnly={locked}
              error={errors.contactPhone}
            />
          )}
        </form.Field>
      </div>
      <form.Field name="active">
        {(field) => (
          <CheckField
            label={t('partners.form.active')}
            hint={t('partners.form.activeHint')}
            checked={field.state.value}
            onChange={field.handleChange}
            disabled={locked}
          />
        )}
      </form.Field>
      {mode === 'edit' && (
        <form.Field name="hidden">
          {(field) => (
            <CheckField
              label={t('partners.form.hidden')}
              hint={t('partners.form.hiddenHint')}
              checked={field.state.value}
              onChange={field.handleChange}
            />
          )}
        </form.Field>
      )}
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
        {pending ? t('saving') : mode === 'create' ? t('partners.form.create') : t('partners.form.save')}
      </Button>
    </form>
  )
}
