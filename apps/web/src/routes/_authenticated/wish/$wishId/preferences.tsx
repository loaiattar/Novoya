import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { localIsoDate } from '@/lib/dates'
import { useDebounced } from '@/hooks/ui/useDebounced'
import { formatList, formatMonthName } from '@/lib/format'

import { ApiError } from '../../../../api/errors'
import {
  answerPanelMutation,
  listMyTripsQueryKey,
  sendCustomRequestMutation,
} from '../../../../api/generated/@tanstack/react-query.gen'
import type { DestinationOut, PanelOut } from '../../../../api/generated/types.gen'
import { type CachedWish, usePanelLimits, wishQueryKey } from '../../../../api/wishes'
import { Button } from '../../../../components/atoms/Button'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { TagGroup } from '../../../../components/molecules/TagGroup'
import { AdvisorChat } from '../../../../components/organisms/AdvisorChat'
import { ConstraintsFields, type ConstraintsValues } from '../../../../components/organisms/ConstraintsFields'
import { IntentAside } from '../../../../components/organisms/IntentAside'
import { NoFitOptions } from '../../../../components/organisms/NoFitOptions'
import { PlanBuilding } from '../../../../components/organisms/PlanBuilding'
import { StickyAction } from '../../../../components/organisms/StickyAction'
import { AppShell } from '../../../../components/templates/AppShell'
import {
  constraintsErrors,
  type ConstraintsErrors,
  MAX_PERSONS,
  MIN_PERSONS,
  parseBudget,
} from '../../../../domain/constraints/constraints'
import {
  answerPanelError,
  initialSelection,
  type Selection,
  selectedTags,
  toggleTag,
} from '../../../../domain/panel/selection'
import { sectionTones } from '../../../../domain/panel/sectionTone'

export const Route = createFileRoute('/_authenticated/wish/$wishId/preferences')({
  component: PreferencesPage,
})

const STEPS = ['preferences', 'preview', 'quote'] as const
const FORM_ID = 'preferences-form'

function PreferencesPage() {
  const { wishId } = Route.useParams()
  const wish = useQueryClient().getQueryData<CachedWish>(wishQueryKey(wishId))
  const { t } = useTranslation('preferences')

  if (wish?.panel) {
    return <PreferencesForm wishId={wishId} text={wish.text} panel={wish.panel} destination={wish.destination} />
  }
  return (
    <AppShell>
      <main className="mx-auto max-w-xl px-5 py-24 text-center">
        <Eyebrow>{t('steps.preferences')}</Eyebrow>
        <h1 className="mb-4 text-display-m">{t('lost.title')}</h1>
        <p className="mb-8 text-muted">
          {t('lost.text')}
        </p>
        <Button asChild variant="coral" size="lg">
          <Link to="/wish">{t('lost.cta')}</Link>
        </Button>
      </main>
    </AppShell>
  )
}

function PreferencesForm({
  wishId,
  text,
  panel,
  destination,
}: {
  wishId: string
  text: string
  panel: PanelOut
  destination: DestinationOut | null
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { t, i18n } = useTranslation('preferences')
  const { t: tErrors } = useTranslation('errors')
  const [selection, setSelection] = useState<Selection>(() => initialSelection(panel.sections))
  const [typed, setConstraints] = useState<ConstraintsValues>({
    budget: '',
    persons: 2,
    startDate: '',
    endDate: '',
  })
  const [errors, setErrors] = useState<ConstraintsErrors>({})

  // What the destination's offers serve (#183). Until it is read, or if it can't be, the usual
  // bounds stay: the answer is still checked when it is sent.
  const limits = usePanelLimits(wishId).data
  // Inside the panel's own 1 to 50, whatever the offers take.
  const within = (persons: number) => Math.min(Math.max(persons, MIN_PERSONS), MAX_PERSONS)
  const minPersons = within(limits?.persons_min ?? MIN_PERSONS)
  const maxPersons = within(limits?.persons_max ?? MAX_PERSONS)
  // The travellers stay inside what the offers take, even when the limits arrive after a choice.
  const constraints = { ...typed, persons: Math.min(Math.max(typed.persons, minPersons), maxPersons) }

  // Travellers and dates the form would send: ask whether at least one offer fits them, by the
  // rule the plan uses. Only a "no" holds the sending; a check still running or failed does not.
  const datesErrors = constraintsErrors(constraints, localIsoDate())
  const ready = !datesErrors.persons && !datesErrors.startDate && !datesErrors.endDate
  // Asked once the values stop changing (300 ms), not on every click (review of #189). A text
  // key, so the same values never restart the wait.
  const asked = ready ? `${constraints.persons}|${constraints.startDate}|${constraints.endDate}` : ''
  const settled = useDebounced(asked, 300)
  const fit = usePanelLimits(wishId, settled ? toCheck(settled) : undefined)
  // Only an answer for what the form holds now counts: during the wait, the last one is old.
  const checked = ready && settled === asked && fit.data?.fits !== undefined && fit.data.fits !== null
  const noFit = checked && fit.data?.fits === false ? noFitMessage(fit.data.open_months) : undefined

  function noFitMessage(months: number[]): string {
    const place = destination?.city ?? destination?.country ?? ''
    const first = t('noFit', { place, count: constraints.persons })
    // The months only help when the trip is outside them: inside, the group or the nights
    // are the reason, and naming the trip's own months would mislead.
    const outside = tripMonths(constraints.startDate, constraints.endDate).some((month) => !months.includes(month))
    if (months.length === 0 || !outside) return first
    const names = months.map((month) => formatMonthName(i18n.language, month))
    return `${first} ${t('openMonths', { months: formatList(i18n.language, names) })}`
  }

  const failure = useRef<HTMLParagraphElement>(null)
  const noFitText = useRef<HTMLParagraphElement>(null)

  // The plan is built while the request runs (up to a minute): the waiting screen replaces the
  // form meanwhile. The answers stay in this component's state, so a failure brings the form
  // back filled in.
  const answer = useMutation(answerPanelMutation())
  const failed = answer.isError
    ? answer.error instanceof ApiError
      ? answerPanelError(answer.error.code, answer.error.status, answer.error.retryAfterSeconds)
      : answerPanelError(undefined, undefined)
    : undefined

  // On a phone the message is below a long form: bring it into view.
  useEffect(() => {
    if (!answer.error) return
    failure.current?.scrollIntoView?.({ block: 'center' })
    failure.current?.focus()
  }, [answer.error])

  // The answers as the API takes them, for these dates.
  const body = (startDate: string, endDate: string) => ({
    selected_tags: selectedTags(selection),
    budget_max: parseBudget(constraints.budget)!,
    currency: 'EUR' as const,
    persons: constraints.persons,
    start_date: startDate,
    end_date: endDate,
  })

  const send = (startDate: string, endDate: string) =>
    answer.mutate(
      { path: { wish_id: wishId }, body: body(startDate, endDate) },
      // Here and not in useMutation: this one does not run once the client has left the page,
      // so a plan ready later never pulls them away from where they went. `replace`: going
      // back must not reopen a panel already answered.
      { onSuccess: (plan) => navigate({ to: '/plans/$planId', params: { planId: plan.id }, replace: true }) },
    )

  // No offer fits (#184): the trip goes to the agency as it is, and an advisor builds it.
  const custom = useMutation({
    ...sendCustomRequestMutation(),
    onSettled: () => queryClient.invalidateQueries({ queryKey: listMyTripsQueryKey() }),
  })
  const sendAnyway = () => {
    const found = constraintsErrors(constraints, localIsoDate())
    setErrors(found)
    if (Object.keys(found).length > 0 || custom.isPending || answer.isPending) return
    custom.mutate(
      { path: { wish_id: wishId }, body: body(constraints.startDate, constraints.endDate) },
      { onSuccess: (plan) => navigate({ to: '/plans/$planId', params: { planId: plan.id }, replace: true }) },
    )
  }

  // Other dates that work: the form shows them, and the plan is built for them at once.
  const pickDates = (startDate: string, endDate: string) => {
    setConstraints({ ...typed, startDate, endDate })
    const found = constraintsErrors({ ...constraints, startDate, endDate }, localIsoDate())
    setErrors(found)
    if (Object.keys(found).length > 0 || answer.isPending || custom.isPending) return
    send(startDate, endDate)
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const found = constraintsErrors(constraints, localIsoDate())
    setErrors(found)
    if (noFit && Object.keys(found).length === 0) {
      // Held: say why where the client is, instead of a button that does nothing.
      noFitText.current?.focus()
      return
    }
    if (Object.keys(found).length > 0 || answer.isPending) return
    send(constraints.startDate, constraints.endDate)
  }

  const tones = sectionTones(panel.sections.map((section) => section.id))
  const labels = new Map(panel.sections.flatMap((section) => section.tags.map((tag) => [`${section.id}:${tag.id}`, tag.label])))
  const picked = selectedTags(selection).map(({ section, tag }) => labels.get(`${section}:${tag}`) ?? tag)

  // The plan was built for no offer after all (the catalog changed since the check): the same
  // ways out as when the check says so.
  const noOfferFits = failed?.key === 'answers.noOfferFits'
  const customFailed = custom.isError && !(custom.error instanceof ApiError && custom.error.status === 401)

  if (answer.isPending || custom.isPending) {
    return (
      <AppShell className="bg-ink">
        <PlanBuilding />
      </AppShell>
    )
  }

  return (
    // Room under the footer for the action bar fixed to the bottom of the screen.
    <AppShell className="pb-22 md:pb-24">
      <div className="md:grid md:min-h-[calc(100vh-88px)] md:grid-cols-[33%_67%]">
        <IntentAside wish={text} steps={STEPS.map((step) => t(`steps.${step}`))} current={0} />
        <main className="bg-paper px-5 pt-[55px] pb-[155px] md:px-[8vw] md:pt-20 md:pb-40">
          <Eyebrow>{t('stepOf', { current: 1, total: STEPS.length })}</Eyebrow>
          <h1 className="mb-[23px] text-display-m">
            {t('titleStart')}
            <br />
            <em>{t('titleEnd')}</em>
          </h1>
          <p className="text-muted">{t('intro')}</p>
          <form id={FORM_ID} onSubmit={submit} noValidate>
            {panel.sections.map((section) => (
              <TagGroup
                key={section.id}
                tone={tones.get(section.id)}
                title={section.title}
                multi={section.multi}
                tags={section.tags}
                selected={selection[section.id] ?? []}
                onToggle={(tagId) => setSelection((current) => toggleTag(current, section, tagId))}
              />
            ))}
            <ConstraintsFields
              values={constraints}
              errors={Object.fromEntries(
                Object.entries(errors).map(([field, key]) => [field, tErrors(key, { min: MIN_PERSONS, max: MAX_PERSONS })]),
              )}
              onChange={(values) => {
                setConstraints(values)
                if (Object.keys(errors).length > 0) setErrors(constraintsErrors(values, localIsoDate()))
              }}
              minPersons={minPersons}
              maxPersons={maxPersons}
              firstDate={limits?.first_date ?? undefined}
              lastDate={limits?.last_date ?? undefined}
              noFit={noFit}
              noFitRef={noFitText}
            />
            {failed && (
              <p ref={failure} tabIndex={-1} role="alert" className="mt-6 text-danger outline-none">
                {tErrors(failed.key, { count: failed.count })}
              </p>
            )}
            {(noFit || noOfferFits) && (
              <NoFitOptions
                wishId={wishId}
                persons={constraints.persons}
                startDate={constraints.startDate}
                endDate={constraints.endDate}
                onPickDates={pickDates}
                onSendAnyway={sendAnyway}
                sending={custom.isPending}
              />
            )}
            {customFailed && (
              <p role="alert" className="mt-4 text-danger">
                {t('noFitOptions.failed')}
              </p>
            )}
          </form>
        </main>
        <StickyAction
          summary={t('picked', { count: picked.length })}
          chips={picked.slice(0, 3)}
          action={
            <Button type="submit" form={FORM_ID} variant="coral" size="lg" className="w-full md:w-auto">
              {t('submit')} <span aria-hidden="true">↗</span>
            </Button>
          }
        />
        <AdvisorChat wishId={wishId} raised />
      </div>
    </AppShell>
  )
}

/** The months (1 to 12) a trip touches, from YYYY-MM-DD dates. */
function tripMonths(start: string, end: string): number[] {
  const months: number[] = []
  let [year, month] = start.split('-').map(Number) as [number, number]
  const [lastYear, lastMonth] = end.split('-').map(Number) as [number, number]
  while ((year < lastYear || (year === lastYear && month <= lastMonth)) && months.length < 12) {
    months.push(month)
    ;[year, month] = month === 12 ? [year + 1, 1] : [year, month + 1]
  }
  return months
}

/** The travellers and dates of a check key, as usePanelLimits takes them. */
function toCheck(key: string): { persons: number; startDate: string; endDate: string } {
  const [persons, startDate, endDate] = key.split('|') as [string, string, string]
  return { persons: Number(persons), startDate, endDate }
}
