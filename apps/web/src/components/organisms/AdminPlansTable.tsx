import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { datesOf, needsAttention, placeOf, type PlanStatus } from '@/domain/admin/activity'
import { formatShortDate } from '@/lib/format'

import { StatusPill } from '../atoms/StatusPill'
import { PersonCell } from '../molecules/PersonCell'

export type AdminPlanRow = {
  id: string
  status: PlanStatus
  country: string | null
  city: string | null
  persons: number | null
  start_date: string | null
  end_date: string | null
  updated_at: string
  client: { name: string | null; email: string } | null
  agent: { name: string | null; email: string } | null
}

type Props = { plans: AdminPlanRow[] }

/** Every client's plans with their status and agent. Each opens the plan, read-only. */
export function AdminPlansTable({ plans }: Props) {
  const { t, i18n } = useTranslation('admin')
  return (
    <table className="w-full border-collapse border-t border-line text-sm">
      <caption className="sr-only">{t('activity.plans.caption')}</caption>
      <thead>
        <tr className="text-xs tracking-widest text-muted uppercase">
          <th scope="col" className="px-2 py-4 text-start font-normal md:p-4">
            {t('activity.plans.trip')}
          </th>
          <th scope="col" className="px-2 py-4 text-start font-normal md:p-4">
            {t('activity.plans.client')}
          </th>
          <th scope="col" className="px-2 py-4 text-start font-normal md:p-4">
            {t('activity.plans.status')}
          </th>
          <th scope="col" className="hidden p-4 text-start font-normal md:table-cell">
            {t('activity.plans.agent')}
          </th>
          <th scope="col" className="hidden p-4 text-start font-normal md:table-cell">
            {t('activity.plans.updated')}
          </th>
        </tr>
      </thead>
      <tbody>
        {plans.map((plan) => {
          const place = placeOf(plan) ?? t('activity.noPlace')
          return (
            <tr key={plan.id} className="border-t border-line align-top">
              <th scope="row" className="px-2 py-4 text-start font-normal md:p-4">
                <span className="grid">
                  <Link
                    to="/admin/activity/plans/$planId"
                    params={{ planId: plan.id }}
                    aria-label={t('activity.plans.open', { place })}
                    className="inline-flex min-h-11 items-center font-semibold underline underline-offset-4"
                  >
                    {place}
                  </Link>
                  <small className="text-xs text-muted">
                    {datesOf(i18n.language, plan) ?? t('activity.noDates')}
                    {plan.persons ? ` · ${t('activity.travellers', { count: plan.persons })}` : ''}
                  </small>
                </span>
              </th>
              <td className="px-2 py-4 md:p-4">
                <PersonCell person={plan.client} fallback={t('activity.noClient')} />
              </td>
              <td className="px-2 py-4 md:p-4">
                <StatusPill highlight={needsAttention(plan.status)}>{t(`activity.planStatus.${plan.status}`)}</StatusPill>
              </td>
              <td className="hidden p-4 md:table-cell">
                <PersonCell person={plan.agent} fallback={t('activity.noAgent')} />
              </td>
              <td className="hidden p-4 md:table-cell">{formatShortDate(i18n.language, plan.updated_at)}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
