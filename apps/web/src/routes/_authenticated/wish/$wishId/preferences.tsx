import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { localIsoDate } from '@/lib/dates'

import { ApiError } from '../../../../api/errors'
import { answerPanelMutation } from '../../../../api/generated/@tanstack/react-query.gen'
import type { PanelOut } from '../../../../api/generated/types.gen'
import { type CachedWish, wishQueryKey } from '../../../../api/wishes'
import { Button } from '../../../../components/atoms/Button'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { TagGroup } from '../../../../components/molecules/TagGroup'
import { ConstraintsFields, type ConstraintsValues } from '../../../../components/organisms/ConstraintsFields'
import { IntentAside } from '../../../../components/organisms/IntentAside'
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
  answerPanelErrorKey,
  initialSelection,
  type Selection,
  selectedTags,
  toggleTag,
} from '../../../../domain/panel/selection'

export const Route = createFileRoute('/_authenticated/wish/$wishId/preferences')({
  component: PreferencesPage,
})

const STEPS = ['preferences', 'preview', 'quote'] as const
const FORM_ID = 'preferences-form'

function PreferencesPage() {
  const { wishId } = Route.useParams()
  const wish = useQueryClient().getQueryData<CachedWish>(wishQueryKey(wishId))
  const { t } = useTranslation('preferences')

  if (wish?.panel) return <PreferencesForm wishId={wishId} text={wish.text} panel={wish.panel} />
  return (
    <AppShell>
      <main className="mx-auto max-w-xl px-5 py-24 text-center">
        <Eyebrow>{t('steps.preferences')}</Eyebrow>
        <h1 className="mb-4 text-[47px] leading-none">{t('lost.title')}</h1>
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

function PreferencesForm({ wishId, text, panel }: { wishId: string; text: string; panel: PanelOut }) {
  const navigate = useNavigate()
  const { t } = useTranslation('preferences')
  const { t: tErrors } = useTranslation('errors')
  const [selection, setSelection] = useState<Selection>(() => initialSelection(panel.sections))
  const [constraints, setConstraints] = useState<ConstraintsValues>({
    budget: '',
    persons: 2,
    startDate: '',
    endDate: '',
  })
  const [errors, setErrors] = useState<ConstraintsErrors>({})

  const failure = useRef<HTMLParagraphElement>(null)

  // The plan is built while the request runs (up to a minute): the waiting screen replaces the
  // form meanwhile. The answers stay in this component's state, so a failure brings the form
  // back filled in.
  const answer = useMutation(answerPanelMutation())

  // On a phone the message is below a long form: bring it into view.
  useEffect(() => {
    if (!answer.error) return
    failure.current?.scrollIntoView?.({ block: 'center' })
    failure.current?.focus()
  }, [answer.error])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const found = constraintsErrors(constraints, localIsoDate())
    setErrors(found)
    if (Object.keys(found).length > 0 || answer.isPending) return
    answer.mutate(
      {
        path: { wish_id: wishId },
        body: {
          selected_tags: selectedTags(selection),
          budget_max: parseBudget(constraints.budget)!,
          currency: 'EUR',
          persons: constraints.persons,
          start_date: constraints.startDate,
          end_date: constraints.endDate,
        },
      },
      // Here and not in useMutation: this one does not run once the client has left the page,
      // so a plan ready later never pulls them away from where they went. `replace`: going
      // back must not reopen a panel already answered.
      { onSuccess: (plan) => navigate({ to: '/plans/$planId', params: { planId: plan.id }, replace: true }) },
    )
  }

  const labels = new Map(panel.sections.flatMap((section) => section.tags.map((tag) => [`${section.id}:${tag.id}`, tag.label])))
  const picked = selectedTags(selection).map(({ section, tag }) => labels.get(`${section}:${tag}`) ?? tag)

  if (answer.isPending) {
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
          <h1 className="mb-[23px] text-[47px] leading-[0.98] md:text-[clamp(56px,5.6vw,82px)]">
            {t('titleStart')}
            <br />
            <em>{t('titleEnd')}</em>
          </h1>
          <p className="text-muted">{t('intro')}</p>
          <form id={FORM_ID} onSubmit={submit} noValidate>
            {panel.sections.map((section) => (
              <TagGroup
                key={section.id}
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
              minPersons={MIN_PERSONS}
              maxPersons={MAX_PERSONS}
            />
            {answer.isError && (
              <p ref={failure} tabIndex={-1} role="alert" className="mt-6 text-danger outline-none">
                {tErrors(
                  answer.error instanceof ApiError
                    ? answerPanelErrorKey(answer.error.code, answer.error.status)
                    : answerPanelErrorKey(undefined, undefined),
                )}
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
      </div>
    </AppShell>
  )
}
