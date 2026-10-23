import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../atoms/Button'
import { Input } from '../atoms/Input'
import { CheckField } from '../molecules/CheckField'
import { TextAreaField } from '../molecules/TextAreaField'
import { TextField } from '../molecules/TextField'

// The limits of the API (accounts/domain/advisor_profile.py).
export const NAME_MAX = 100
export const TITLE_MAX = 60
export const SUMMARY_MAX = 140
export const SERVICE_MAX = 40
export const SERVICES_MAX = 6

export type AdvisorService = { fr: string; en: string }

export type AdvisorFields = {
  publicName: string
  title: string
  summary: string
  services: AdvisorService[]
  consent: boolean
  shown: boolean
}

type Props = {
  initialValues: AdvisorFields
  /** Resolves once saved. Rejects when the API refuses: the values stay as typed. */
  onSubmit: (values: AdvisorFields) => Promise<unknown>
  onCancel: () => void
  pending?: boolean
  /** Why the API refused the last save. */
  error?: string
}

/**
 * An agent's public profile: what the home page shows of them. Each service is typed in French,
 * in English or both; shown on the home page only once the agent agreed to it.
 */
export function AdvisorForm({ initialValues, onSubmit, onCancel, pending = false, error }: Props) {
  const { t } = useTranslation('admin')
  const [values, setValues] = useState(initialValues)
  const [checked, setChecked] = useState(false)
  const set = <K extends keyof AdvisorFields>(key: K, value: AdvisorFields[K]) =>
    setValues((current) => ({ ...current, [key]: value }))
  const setService = (index: number, service: AdvisorService) =>
    set('services', values.services.map((current, i) => (i === index ? service : current)))

  const nameMissing = values.publicName.trim() === ''
  const servicesMissingLanguage = values.services.map((s) => s.fr.trim() === '' && s.en.trim() === '')
  const valid = !nameMissing && !servicesMissingLanguage.some(Boolean)

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        setChecked(true)
        if (pending || !valid) return
        onSubmit(values).catch(() => {
          // The page shows why; keep what was typed.
        })
      }}
      className="max-w-2xl"
    >
      <TextField
        label={t('advisors.form.publicName')}
        hint={t('advisors.form.publicNameHint')}
        value={values.publicName}
        onChange={(value) => set('publicName', value)}
        maxLength={NAME_MAX}
        required
        error={checked && nameMissing ? t('advisors.form.publicNameMissing') : undefined}
      />
      <TextField
        label={t('advisors.form.title')}
        hint={t('advisors.form.titleHint')}
        value={values.title}
        onChange={(value) => set('title', value)}
        maxLength={TITLE_MAX}
      />
      <TextAreaField
        label={t('advisors.form.summary')}
        hint={t('advisors.form.summaryHint', { count: values.summary.length, max: SUMMARY_MAX })}
        value={values.summary}
        onChange={(value) => set('summary', value)}
        maxLength={SUMMARY_MAX}
      />

      <fieldset className="mt-6 mb-4 border-0 p-0">
        <legend className="mb-1 text-sm font-semibold">{t('advisors.form.services')}</legend>
        <p className="mt-0 mb-3 text-xs text-muted">{t('advisors.form.servicesHint', { max: SERVICES_MAX })}</p>
        <ul className="m-0 grid list-none gap-3 p-0">
          {values.services.map((service, index) => {
            const missing = checked && servicesMissingLanguage[index]
            const errorId = `advisor-service-${index}-error`
            return (
              <li key={index} className="grid gap-2 md:grid-cols-[1fr_1fr_auto] md:items-center">
                <Input
                  aria-label={t('advisors.form.serviceFr', { number: index + 1 })}
                  lang="fr"
                  value={service.fr}
                  maxLength={SERVICE_MAX}
                  placeholder={t('advisors.form.serviceFrPlaceholder')}
                  onChange={(event) => setService(index, { ...service, fr: event.target.value })}
                  aria-invalid={missing || undefined}
                  aria-describedby={missing ? errorId : undefined}
                />
                <Input
                  aria-label={t('advisors.form.serviceEn', { number: index + 1 })}
                  lang="en"
                  value={service.en}
                  maxLength={SERVICE_MAX}
                  placeholder={t('advisors.form.serviceEnPlaceholder')}
                  onChange={(event) => setService(index, { ...service, en: event.target.value })}
                  aria-invalid={missing || undefined}
                  aria-describedby={missing ? errorId : undefined}
                />
                <Button
                  type="button"
                  variant="link"
                  className="min-h-11 justify-self-start"
                  onClick={() => set('services', values.services.filter((_, i) => i !== index))}
                >
                  {t('advisors.form.removeService', { number: index + 1 })}
                </Button>
                {missing && (
                  <p id={errorId} className="m-0 text-sm text-danger md:col-span-3">
                    {t('advisors.form.serviceMissing')}
                  </p>
                )}
              </li>
            )
          })}
        </ul>
        {values.services.length < SERVICES_MAX && (
          <Button
            type="button"
            variant="outline"
            className="mt-3"
            onClick={() => set('services', [...values.services, { fr: '', en: '' }])}
          >
            {t('advisors.form.addService')}
          </Button>
        )}
      </fieldset>

      <CheckField
        label={t('advisors.form.consent')}
        hint={t('advisors.form.consentHint')}
        checked={values.consent}
        // Taking the agreement back hides the profile too.
        onChange={(consent) => setValues((current) => ({ ...current, consent, shown: consent && current.shown }))}
      />
      <CheckField
        label={t('advisors.form.shown')}
        hint={values.consent ? t('advisors.form.shownHint') : t('advisors.form.shownNeedsConsent')}
        checked={values.shown}
        disabled={!values.consent}
        onChange={(shown) => set('shown', shown)}
      />

      {error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {error}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-3">
        <Button type="submit" disabled={pending}>
          {pending ? t('saving') : t('advisors.form.save')}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t('advisors.form.cancel')}
        </Button>
      </div>
    </form>
  )
}
