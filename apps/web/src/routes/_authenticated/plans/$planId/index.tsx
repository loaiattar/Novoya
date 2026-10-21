import { createFileRoute, notFound } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { Button } from '../../../../components/atoms/Button'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { ConversationDock } from '../../../../components/organisms/ConversationDock'
import { DayTimeline } from '../../../../components/organisms/DayTimeline'
import { PlanHeader } from '../../../../components/organisms/PlanHeader'
import { AppShell } from '../../../../components/templates/AppShell'
import { DemoBanner } from '../../../../components/molecules/DemoBanner'
import { getPlan } from '../../../../fixtures/plans'
import { PlanNotes } from '../../../../components/molecules/PlanNotes'

export const Route = createFileRoute('/_authenticated/plans/$planId/')({
  loader: ({ params }) => {
    const plan = getPlan(params.planId)
    if (!plan) throw notFound()
    return plan
  },
  notFoundComponent: NotFound,
  component: PlanPage,
})

function NotFound() {
  const { t } = useTranslation('plan')
  return <p className="px-5 pt-32 md:px-[8vw]">{t('notFound')}</p>
}

function PlanPage() {
  const plan = Route.useLoaderData()
  const { t } = useTranslation('plan')
  return (
    <AppShell>
      <DemoBanner />
      <main className="lg:pb-24">
        <PlanHeader {...plan} />
        <DayTimeline planId={plan.id} days={plan.days} />
         <PlanNotes basedOnPreferences={plan.basedOnPreferences} />
        <DayTimeline planId={plan.id} days={plan.days} />
        <section className="bg-ink px-6 py-15 text-white md:flex md:items-end md:justify-between md:px-[8vw] md:py-20">
          <div className="max-w-[660px]">
            <Eyebrow light>{t('cta.eyebrow')}</Eyebrow>
            <h2 className="mb-4 text-[43px] leading-tight md:text-[56px]">{t('cta.title')}</h2>
            <p className="leading-relaxed text-white/70">
              {t('cta.text')}
            </p>
          </div>
          {/* Asking for a quote is #50: until then the plan never leads to a price (#31). */}
          <div className="mt-6 grid gap-2 md:mt-0 md:justify-items-end">
            <Button variant="coral" size="lg" disabled className="w-full md:w-auto">
              {t('cta.button')}
            </Button>
            <small className="text-sm text-white/80">{t('cta.unavailable')}</small>
          </div>
        </section>
        <ConversationDock version={plan.version} />
      </main>
    </AppShell>
  )
}
