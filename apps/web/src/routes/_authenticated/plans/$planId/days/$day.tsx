import { createFileRoute, Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { Plan } from '../../../../../api/generated/types.gen'
import { usePlan } from '../../../../../api/plans'
import { Eyebrow } from '../../../../../components/atoms/Eyebrow'
import { ErrorNote } from '../../../../../components/molecules/ErrorNote'
import { PlanItem } from '../../../../../components/molecules/PlanItem'
import { AppShell } from '../../../../../components/templates/AppShell'
import { groupByDay } from '../../../../../domain/plan/days'

export const Route = createFileRoute('/_authenticated/plans/$planId/days/$day')({
  component: DayRoute,
})

/** A day of the plan, as GET /plans/{id} gives it: the same query as the plan page, so it is cached. */
function DayRoute() {
  const { planId, day } = Route.useParams()
  const { t } = useTranslation('plan')
  const { plan, signedOut, missing } = usePlan(
    planId,
    `/plans/${encodeURIComponent(planId)}/days/${encodeURIComponent(day)}`,
  )

  return (
    <AppShell>
      {plan.isPending || signedOut ? (
        <p className="px-5 pt-32 text-muted md:px-[8vw]">{t('live.loading')}</p>
      ) : missing ? (
        <NotFound message={t('notFound')} />
      ) : plan.data ? (
        // Kept when reading it again in the background fails: what is on screen is still right.
        <LiveDay plan={plan.data} day={day} />
      ) : plan.isFetching ? (
        // Trying again after a failure: the click shows that something happens.
        <p className="px-5 pt-32 text-muted md:px-[8vw]">{t('live.loading')}</p>
      ) : (
        <ErrorNote message={t('live.loadFailed')} onRetry={() => plan.refetch()} />
      )}
    </AppShell>
  )
}

function NotFound({ message }: { message: string }) {
  return <p className="px-5 pt-32 md:px-[8vw]">{message}</p>
}

function LiveDay({ plan, day }: { plan: Plan; day: string }) {
  const { t } = useTranslation('plan')
  // A day of the trip is a day with offers, as on the plan page.
  const days = groupByDay(plan.items)
  const index = days.findIndex((item) => String(item.day) === day)
  if (index === -1) return <NotFound message={t('day.notFound')} />
  const { day: number, items } = days[index]
  const previous = days[index - 1]
  const next = days[index + 1]

  return (
    <main className="px-5 pb-16 md:px-[8vw] md:pb-24">
      <Link
        to="/plans/$planId"
        params={{ planId: plan.id }}
        className="my-4 inline-flex min-h-11 items-center text-ink underline underline-offset-4 md:my-6"
      >
        {t('day.back')}
      </Link>
      <section className="pt-8 md:pt-12">
        <Eyebrow>{t('live.eyebrow')}</Eyebrow>
        <h1 className="m-0 text-display-l">{t('live.day', { number })}</h1>
      </section>
      <ul className="mt-10 grid gap-8 border-t border-line pt-8 md:mt-14 md:grid-cols-2 md:gap-10">
        {items.map((item) => (
          <li key={item.id} className="min-w-0">
            <PlanItem item={item} />
          </li>
        ))}
      </ul>
      <nav aria-label={t('daysLabel')} className="mt-14 flex flex-wrap justify-between gap-4">
        {previous && (
          <Link
            to="/plans/$planId/days/$day"
            params={{ planId: plan.id, day: String(previous.day) }}
            className="inline-flex min-h-11 items-center underline underline-offset-4"
          >
            {t('day.previous', { number: previous.day })}
          </Link>
        )}
        {next && (
          <Link
            to="/plans/$planId/days/$day"
            params={{ planId: plan.id, day: String(next.day) }}
            className="ml-auto inline-flex min-h-11 items-center underline underline-offset-4"
          >
            {t('day.next', { number: next.day })}
          </Link>
        )}
      </nav>
    </main>
  )
}
