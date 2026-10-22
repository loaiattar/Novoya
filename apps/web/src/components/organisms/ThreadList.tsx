import { useTranslation } from 'react-i18next'

import { formatDateTime, formatDayRange, formatMonth } from '@/lib/format'
import { cn } from '@/lib/utils'

import { StatusPill } from '../atoms/StatusPill'

export type ThreadStatus = 'offer_sent' | 'preview_proposed' | 'in_discussion' | 'accepted' | 'refused'

export type ThreadSummary = {
  id: string
  photo: string
  status: ThreadStatus
  highlight?: boolean
  country: string
  /** A range, a month (dates not set yet), or nothing yet. */
  dates: { start: string; end: string } | { month: string } | null
  title: string
  /** The current preview's version, or null for a draft. */
  version: number | null
  /** ISO date and time of the last change. */
  updatedAt: string
}

type Props = {
  threads: ThreadSummary[]
  selectedId: string
  onSelect: (id: string) => void
}

/** The client's trips, one card each. Choosing one shows its details. */
export function ThreadList({ threads, selectedId, onSelect }: Props) {
  const { t, i18n } = useTranslation('trips')
  const locale = i18n.language
  const when = (dates: ThreadSummary['dates']) =>
    dates === null
      ? t('datesToBeSet')
      : 'month' in dates
        ? formatMonth(locale, dates.month)
        : formatDayRange(locale, dates.start, dates.end)
  return (
    <ul aria-label={t('listLabel')} className="flex flex-col gap-2">
      {threads.map((thread) => {
        const selected = thread.id === selectedId
        return (
          <li key={thread.id}>
            <button
              type="button"
              aria-current={selected ? 'true' : undefined}
              onClick={() => onSelect(thread.id)}
              className={cn(
                'grid w-full grid-cols-[75px_1fr] items-center gap-3.5 border border-line bg-white p-3 text-left sm:grid-cols-[100px_1fr_auto]',
                selected && 'border-ink shadow-[inset_3px_0_var(--color-coral)]',
              )}
            >
              <img src={thread.photo} alt="" className="block h-20 w-full object-cover sm:h-25" />
              <span className="grid justify-items-start">
                <StatusPill highlight={thread.highlight} className="mb-2">
                  {t(`status.${thread.status}`)}
                </StatusPill>
                <small className="text-xs text-muted">
                  {t('placeAndDates', { country: thread.country, dates: when(thread.dates) })}
                </small>
                <b className="my-1 font-serif text-[17px] font-normal">{thread.title}</b>
                <span className="text-xs text-muted">
                  {thread.version === null ? t('draftSummary') : t('previewSummary', { version: thread.version })}
                </span>
              </span>
              <time dateTime={thread.updatedAt} className="hidden self-start text-xs text-muted sm:block">
                {formatDateTime(locale, thread.updatedAt)}
              </time>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
