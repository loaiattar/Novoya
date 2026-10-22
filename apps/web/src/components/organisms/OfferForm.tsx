import { useForm } from '@tanstack/react-form'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { formatMonthName } from '@/lib/format'

import { Button } from '../atoms/Button'
import { CheckField } from '../molecules/CheckField'
import { SelectField } from '../molecules/SelectField'
import { TextAreaField } from '../molecules/TextAreaField'
import { TextField } from '../molecules/TextField'
import { type CatalogKind, KINDS, MONTHS, PRICE_UNITS, type PriceUnit } from './catalog'

export type OfferFields = {
  kind: CatalogKind
  title: string
  description: string
  country: string
  city: string
  minPersons: string
  maxPersons: string
  availableFrom: string
  availableTo: string
  tags: string
  featured: boolean
  active: boolean
  hidden: boolean
  price: string
  priceUnit: PriceUnit | ''
  openingMonths: number[]
  conditions: string
  restrictions: string
  cancellation: string
  confirmationDelayHours: string
}

type TextName = {
  [K in keyof OfferFields]: OfferFields[K] extends string ? K : never
}[keyof OfferFields]

type Props = {
  initialValues: OfferFields
  /** create: a new offer (it starts shown); edit: an existing one, which can be hidden. */
  mode: 'create' | 'edit'
  /** Its partner comes from the agency's own system: only featured and hidden change here. */
  imported?: boolean
  /** Resolves once saved. Rejects when the values are refused: they stay as typed. */
  onSubmit: (values: OfferFields) => Promise<unknown>
  pending?: boolean
  /** Why the last attempt failed: next to its field, or for the whole form. */
  errors?: Partial<Record<keyof OfferFields | 'form', string>>
  /** Said once saved. */
  success?: string
}

/** An offer: what it is, where, for how many and when, its tags, price and terms. */
export function OfferForm({ initialValues, mode, imported = false, onSubmit, pending = false, errors = {}, success }: Props) {
  const { t, i18n } = useTranslation('admin')
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
  const monthsId = useId()

  const text = (
    name: TextName,
    options: { type?: 'text' | 'date'; numeric?: boolean; hint?: string; multiline?: boolean } = {},
  ) => (
    <form.Field name={name}>
      {(field) =>
        options.multiline ? (
          <TextAreaField
            label={t(`offers.form.${name}`)}
            hint={options.hint}
            value={field.state.value as string}
            onChange={field.handleChange}
            onBlur={field.handleBlur}
            readOnly={locked}
            error={errors[name]}
          />
        ) : (
          <TextField
            label={t(`offers.form.${name}`)}
            type={options.type}
            inputMode={options.numeric ? 'numeric' : undefined}
            name={field.name}
            hint={options.hint}
            value={field.state.value as string}
            onChange={field.handleChange}
            onBlur={field.handleBlur}
            readOnly={locked}
            error={errors[name]}
          />
        )
      }
    </form.Field>
  )

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        void form.handleSubmit()
      }}
      className="max-w-2xl"
    >
      {imported && <p className="mb-4 border-s-2 border-coral bg-ivory p-4 text-sm">{t('offers.form.importedNote')}</p>}
      <form.Field name="kind">
        {(field) => (
          <SelectField<CatalogKind>
            label={t('offers.form.kind')}
            value={field.state.value}
            options={KINDS.map((kind) => ({ value: kind, label: t(`kinds.${kind}`) }))}
            onChange={(kind) => kind && field.handleChange(kind)}
            disabled={locked}
            error={errors.kind}
          />
        )}
      </form.Field>
      {text('title')}
      {text('description', { multiline: true })}
      <div className="md:grid md:grid-cols-2 md:gap-x-5">
        {text('country')}
        {text('city')}
        {text('minPersons', { numeric: true })}
        {text('maxPersons', { numeric: true })}
        {text('availableFrom', { type: 'date' })}
        {text('availableTo', { type: 'date' })}
      </div>
      {text('tags', { multiline: true, hint: t('offers.form.tagsHint') })}
      <div className="md:grid md:grid-cols-2 md:gap-x-5">
        {text('price', { numeric: true })}
        <form.Field name="priceUnit">
          {(field) => (
            <SelectField<PriceUnit>
              label={t('offers.form.priceUnit')}
              value={field.state.value}
              options={[
                { value: '', label: t('offers.form.noUnit') },
                ...PRICE_UNITS.map((unit) => ({ value: unit, label: t(`units.${unit}`) })),
              ]}
              onChange={field.handleChange}
              disabled={locked}
              error={errors.priceUnit}
            />
          )}
        </form.Field>
      </div>
      <form.Field name="openingMonths">
        {(field) => (
          <fieldset className="my-4" aria-describedby={errors.openingMonths ? `${monthsId}-error` : `${monthsId}-hint`}>
            <legend className="mb-2 text-sm">{t('offers.form.openingMonths')}</legend>
            <p id={`${monthsId}-hint`} className="mb-2 text-xs text-muted">
              {t('offers.form.openingMonthsHint')}
            </p>
            <div className="grid grid-cols-2 gap-x-4 sm:grid-cols-3 md:grid-cols-4">
              {MONTHS.map((month) => (
                <CheckField
                  key={month}
                  className="my-0"
                  label={formatMonthName(i18n.language, month)}
                  checked={field.state.value.includes(month)}
                  disabled={locked}
                  onChange={(checked) =>
                    field.handleChange(
                      checked ? [...field.state.value, month] : field.state.value.filter((value) => value !== month),
                    )
                  }
                />
              ))}
            </div>
            {errors.openingMonths && (
              <p id={`${monthsId}-error`} className="mt-1.5 text-sm text-danger">
                {errors.openingMonths}
              </p>
            )}
          </fieldset>
        )}
      </form.Field>
      {text('conditions', { multiline: true })}
      {text('restrictions', { multiline: true })}
      {text('cancellation', { multiline: true })}
      {text('confirmationDelayHours', {
        numeric: true,
        hint: mode === 'edit' && !locked ? t('offers.form.delayHint') : undefined,
      })}
      <form.Field name="featured">
        {(field) => (
          <CheckField
            label={t('offers.form.featured')}
            hint={t('offers.form.featuredHint')}
            checked={field.state.value}
            onChange={field.handleChange}
          />
        )}
      </form.Field>
      <form.Field name="active">
        {(field) => (
          <CheckField
            label={t('offers.form.active')}
            hint={t('offers.form.activeHint')}
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
              label={t('offers.form.hidden')}
              hint={t('offers.form.hiddenHint')}
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
        {pending ? t('saving') : mode === 'create' ? t('offers.form.create') : t('offers.form.save')}
      </Button>
    </form>
  )
}
