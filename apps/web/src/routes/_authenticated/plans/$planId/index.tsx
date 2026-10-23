import { createFileRoute, Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import type { ReactNode } from 'react'

import { ApiError } from '../../../../api/errors'
import type { Plan } from '../../../../api/generated/types.gen'
import { usePlan, useSendToAgency } from '../../../../api/plans'
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../../../../components/ui/alert-dialog'
import { tripStatus } from '../../../../domain/trips/trip'
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
        <h1 className="m-0 text-display-m">
          {t('live.titleStart')}{' '}
          <br />
          <em>{t('live.titleEnd')}</em>
        </h1>
        <p className="mt-8 max-w-[660px] font-serif text-lg leading-relaxed">{plan.summary}</p>
        {!plan.based_on_preferences && <p className="mt-4 max-w-[660px] text-sm text-muted">{t('live.noPreferences')}</p>}
      </section>
      <PlanDays planId={plan.id} items={plan.items} />
      <QuoteNote />
      <QuoteCall>
        <SendToAgency plan={plan} />
      </QuoteCall>
      <AdvisorChat wishId={plan.wish_id} />
    </main>
  )
}

function DemoPlanPage() {
  const { t } = useTranslation('plan')
  const plan = getPlan(DEMO_PLAN_ID)!
  return (
    <AppShell>
      <DemoBanner />
      <main>
        <PlanHeader {...plan} />
        <DayTimeline days={plan.days} />
        <QuoteNote />
        <QuoteCall>
          {/* The demo plan is not in the API: it can never be sent, nor lead to a price (#31). */}
          <Button variant="coral" size="lg" disabled className="w-full md:w-auto">
            {t('cta.button')}
          </Button>
          <small className="text-sm text-white/80">{t('cta.demo')}</small>
        </QuoteCall>
      </main>
    </AppShell>
  )
}

function QuoteCall({ children }: { children: ReactNode }) {
  const { t } = useTranslation('plan')
  return (
    <section className="bg-ink px-6 py-15 text-white md:flex md:items-end md:justify-between md:gap-10 md:px-[8vw] md:py-20">
      <div className="max-w-[660px]">
        <Eyebrow light>{t('cta.eyebrow')}</Eyebrow>
        <h2 className="mb-4 text-display-m">{t('cta.title')}</h2>
        <p className="leading-relaxed text-white/70">{t('cta.text')}</p>
      </div>
      <div className="mt-6 grid gap-2 md:mt-0 md:max-w-[360px] md:justify-items-end md:text-right">{children}</div>
    </section>
  )
}

/**
 * The "Send to the agency" button and its confirmation step, while the plan is proposed. Once
 * sent, where it stands: sent with the answer time, then an advisor working on it. The answer
 * time is the API's setting, never written in the text.
 */
function SendToAgency({ plan }: { plan: Plan }) {
  const { t } = useTranslation('plan')
  const { t: tTrips } = useTranslation('trips')
  const send = useSendToAgency(plan.id, `/plans/${encodeURIComponent(plan.id)}`)
  const days = plan.answer_within_days

  if (plan.status !== 'proposed') {
    return (
      <>
        <p role="status" className="text-lg">
          {plan.status === 'requested'
            ? t('cta.sent', { count: days })
            : plan.status === 'negotiating'
              ? t('cta.inProgress')
              : // Quoted, accepted or rejected: the same words as My trips.
                tTrips(`status.${tripStatus({ status: 'planned', plan_status: plan.status })}`)}
        </p>
        <Link to="/trips" className="text-sm text-white/80 underline underline-offset-4 hover:text-white">
          {t('cta.followOnTrips')}
        </Link>
      </>
    )
  }

  // A 409 means it was sent already: the plan is read again and shows it, so no error then.
  // A 401 goes to the sign-in page instead.
  const failed = send.isError && !(send.error instanceof ApiError && [401, 409].includes(send.error.status))
  return (
    <>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button variant="coral" size="lg" className="w-full md:w-auto" disabled={send.isPending}>
            {send.isPending ? t('cta.sending') : t('cta.button')}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent className="rounded-none border-line bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif text-2xl font-normal tracking-normal">
              {t('cta.confirmTitle')}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-muted">{t('cta.confirmBody', { count: days })}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="min-h-11 rounded-full">{t('cta.confirmCancel')}</AlertDialogCancel>
            <AlertDialogAction className="min-h-11 rounded-full" onClick={() => send.mutate()}>
              {t('cta.confirmAction')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {failed && (
        <p role="alert" className="text-sm text-white">
          {t('cta.failed')}
        </p>
      )}
    </>
  )
}
