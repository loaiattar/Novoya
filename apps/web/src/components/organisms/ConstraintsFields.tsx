import { type Ref, useId } from 'react'
import { useTranslation } from 'react-i18next'

import { localIsoDate } from '@/lib/dates'

import { Eyebrow } from '../atoms/Eyebrow'
import { Input } from '../atoms/Input'
import { Field } from '../molecules/Field'
import { Stepper } from '../molecules/Stepper'

export type ConstraintsValues = { budget: string; persons: number; startDate: string; endDate: string }

type Props = {
  values: ConstraintsValues
  errors: Partial<Record<keyof ConstraintsValues, string>>
  onChange: (values: ConstraintsValues) => void
  minPersons: number
  maxPersons: number
  /** The first and last dates the destination's offers serve (#183); none: from today, no end. */
  firstDate?: string
  lastDate?: string
  /** Why these travellers and dates fit no offer: announced, and linked to both. */
  noFit?: string
  /** Where the page moves the focus when the message holds the sending. */
  noFitRef?: Ref<HTMLParagraphElement>
}

const label = 'text-xs tracking-[0.12em] uppercase'

/** The panel's last step: budget, travellers and dates. */
export function ConstraintsFields({
  values,
  errors,
  onChange,
  minPersons,
  maxPersons,
  firstDate,
  lastDate,
  noFit,
  noFitRef,
}: Props) {
  const personsId = useId()
  const { t } = useTranslation('preferences')
  const set = <K extends keyof ConstraintsValues>(key: K, value: ConstraintsValues[K]) =>
    onChange({ ...values, [key]: value })
  const today = localIsoDate()
  // The plan needs one open day in the trip (#182), so the pickers allow every trip that
  // overlaps the offers' season (review of #189): the departure up to the last open day, the
  // return from the first one. ISO dates compare as text.
  // The server's day is UTC: its last date can be yesterday here. Then no end is set.
  const latest = lastDate && lastDate >= today ? lastDate : undefined
  const departure = values.startDate || today
  const earliestReturn = firstDate && firstDate > departure ? firstDate : departure
  const noFitId = `${personsId}-no-fit`
  const withNoFit = (ids?: string) => [ids, noFit ? noFitId : undefined].filter(Boolean).join(' ') || undefined

  return (
    <section aria-labelledby={`${personsId}-title`} className="mt-[50px] border-t border-ink pt-10">
      <Eyebrow>
        <span id={`${personsId}-title`}>{t('lastMarkers')}</span>
      </Eyebrow>
      <div className="grid gap-x-5 md:grid-cols-2">
        <Field
          label={<span className={label}>{t('budget')}</span>}
          hint={t('budgetHint')}
          error={errors.budget}
          className="my-2.5"
        >
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              inputMode="decimal"
              placeholder={t('budgetPlaceholder')}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              value={values.budget}
              onChange={(event) => set('budget', event.target.value)}
            />
          )}
        </Field>
        <div className="my-2.5">
          <p id={`${personsId}-label`} className={`mb-2 ${label}`}>
            {t('travellers')}
          </p>
          <div aria-labelledby={`${personsId}-label`} role="group">
            <Stepper
              value={values.persons}
              min={minPersons}
              max={maxPersons}
              decreaseLabel={t('fewerTravellers')}
              increaseLabel={t('moreTravellers')}
              valueText={t('persons', { count: values.persons })}
              describedBy={withNoFit(errors.persons ? `${personsId}-error` : undefined)}
              onChange={(persons) => set('persons', persons)}
            />
          </div>
          {errors.persons && (
            <p id={`${personsId}-error`} className="mt-1.5 text-sm text-danger">
              {errors.persons}
            </p>
          )}
        </div>
        <Field label={<span className={label}>{t('departure')}</span>} error={errors.startDate} className="my-2.5">
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              type="date"
              aria-describedby={withNoFit(describedBy)}
              aria-invalid={invalid}
              min={today}
              max={latest}
              value={values.startDate}
              onChange={(event) => set('startDate', event.target.value)}
            />
          )}
        </Field>
        <Field label={<span className={label}>{t('return')}</span>} error={errors.endDate} className="my-2.5">
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              type="date"
              min={earliestReturn}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              value={values.endDate}
              onChange={(event) => set('endDate', event.target.value)}
            />
          )}
        </Field>
      </div>
      {/* Announced when it appears; the travellers or the dates can be the reason. */}
      <p
        id={noFitId}
        ref={noFitRef}
        tabIndex={-1}
        aria-live="polite"
        className={noFit ? 'mt-1.5 text-sm text-danger outline-none' : 'sr-only'}
      >
        {noFit}
      </p>
    </section>
  )
}
