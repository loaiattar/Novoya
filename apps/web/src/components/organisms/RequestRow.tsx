import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { QueueEntry } from '@/api/generated/types.gen'
import { formatDayRange, formatEuros } from '@/lib/format'

import { Button } from '../atoms/Button'
import { StatusPill } from '../atoms/StatusPill'

type Props = {
  entry: QueueEntry
  /** For a plan waiting to be taken. The others link to their page instead. */
  onTake?: () => void
  taking?: boolean
}

/** One plan in the agency queue: the client's wish, where, when, for how many, the budget. */
export function RequestRow({ entry, onTake, taking = false }: Props) {
  const { t, i18n } = useTranslation('agent')
  const locale = i18n.language
  const place =
    entry.city && entry.country
      ? t('request.place', { city: entry.city, country: entry.country })
      : (entry.city ?? entry.country)
  const waiting = entry.status === 'requested'
  return (
    <article className="grid gap-x-5 gap-y-3 border-b border-line py-6 xl:grid-cols-[1fr_180px_150px] xl:items-center">
      <div className="min-w-0">
        {place && <small className="text-xs text-muted">{place}</small>}
        <h2 className="my-2 font-serif text-xl tracking-normal">
          {waiting ? (
            entry.summary
          ) : (
            <Link to="/agent/plans/$planId" params={{ planId: entry.id }}>
              {entry.summary}
            </Link>
          )}
        </h2>
        {entry.wish_text && <p className="m-0 text-sm text-muted">“{entry.wish_text}”</p>}
      </div>
      <dl className="m-0 grid">
        <dt className="text-xs text-muted">{t('request.budgetMax')}</dt>
        <dd className="m-0 my-1 font-serif">
          {entry.budget_max === null ? t('request.noBudget') : formatEuros(locale, Number(entry.budget_max))}
        </dd>
        {entry.start_date && entry.end_date && (
          <dd className="m-0 text-xs text-muted">
            {t('request.datesTravellers', {
              dates: formatDayRange(locale, entry.start_date, entry.end_date),
              count: entry.persons ?? 1,
            })}
          </dd>
        )}
      </dl>
      <div className="grid justify-items-start">
        {waiting ? (
          <Button className="w-full md:w-auto" disabled={!onTake || taking} onClick={onTake}>
            {t('request.take')}
          </Button>
        ) : (
          <StatusPill highlight={entry.status === 'negotiating'}>{t(`status.${entry.status}`)}</StatusPill>
        )}
      </div>
    </article>
  )
}
