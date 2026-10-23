import { createFileRoute } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { Plan } from '../../../../api/generated/types.gen'
import { usePlan } from '../../../../api/plans'
import { Button } from '../../../../components/atoms/Button'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { DemoBanner } from '../../../../components/molecules/DemoBanner'
import { ErrorNote } from '../../../../components/molecules/ErrorNote'
import { QuoteNote } from '../../../../components/molecules/QuoteNote'
import { AdvisorChat } from '../../../../components/organisms/AdvisorChat'
import { DayTimeline } from '../../../../components/organisms/DayTimeline'
import { PlanDays } from '../../../../components/organisms/PlanDays'
import { PlanHeader } from '../../../../components/organisms/PlanHeader'
import { AppShell } from '../../../../components/templates/AppShell'
import { DEMO_PLAN_ID, getPlan } from '../../../../fixtures/plans'

export const Route = createFileRoute('/_authenticated/plans/$planId/')({
  component: PlanRoute,
})

// The demo plan stays for the demo trips (/trips); every other id is read from the API.
function PlanRoute() {
  const { planId } = Route.useParams()
  return planId === DEMO_PLAN_ID ? <DemoPlanPage /> : <PlanPage planId={planId} />
}

function NotFound() {
  const { t } = useTranslation('plan')
  return <p className="px-5 pt-32 md:px-[8vw]">{t('notFound')}</p>
}

/** The plan built from the client's answers, as GET /plans/{id} gives it. */
function PlanPage({ planId }: { planId: string }) {
  const { t } = useTranslation('plan')
  const { plan, signedOut, missing } = usePlan(planId, `/plans/${encodeURIComponent(planId)}`)

  return (
    <AppShell>
      {plan.isPending || signedOut ? (
        <p className="px-5 pt-32 text-muted md:px-[8vw]">{t('live.loading')}</p>
      ) : missing ? (
        <NotFound />
      ) : plan.data ? (
        // Kept when reading it again in the background fails: what is on screen is still right.
        <LivePlan plan={plan.data} />
      ) : plan.isFetching ? (
        // Trying again after a failure: the click shows that something happens.
        <p className="px-5 pt-32 text-muted md:px-[8vw]">{t('live.loading')}</p>
      ) : (
        <ErrorNote message={t('live.loadFailed')} onRetry={() => plan.refetch()} />
      )}
    </AppShell>
  )
}

function LivePlan({ plan }: { plan: Plan }) {
  const { t } = useTranslation('plan')
  return (
    <main>
      <section className="bg-ivory px-5 pt-16 pb-10 md:px-[8vw] md:pt-25 md:pb-20">
        <Eyebrow>{t('live.eyebrow')}</Eyebrow>
        <h1 className="m-0 text-[47px] leading-[0.98] md:text-[clamp(56px,5.6vw,82px)]">
          {t('live.titleStart')}{' '}
          <br />
          <em>{t('live.titleEnd')}</em>
        </h1>
        <p className="mt-8 max-w-[660px] font-serif text-lg leading-relaxed">{plan.summary}</p>
        {!plan.based_on_preferences && <p className="mt-4 max-w-[660px] text-sm text-muted">{t('live.noPreferences')}</p>}
      </section>
      <PlanDays planId={plan.id} items={plan.items} />
      <QuoteNote />
      <QuoteCall />
      <AdvisorChat wishId={plan.wish_id} />
    </main>
  )
}

function DemoPlanPage() {
  const plan = getPlan(DEMO_PLAN_ID)!
  return (
    <AppShell>
      <DemoBanner />
      <main>
        <PlanHeader {...plan} />
        <DayTimeline days={plan.days} />
        <QuoteNote />
        <QuoteCall />
      </main>
    </AppShell>
  )
}

function QuoteCall() {
  const { t } = useTranslation('plan')
  return (
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
  )
}
