import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { datesOf, needsAttention, placeOf, type QuoteStatus } from '@/domain/admin/activity'
import { formatEuros, formatShortDate } from '@/lib/format'

import { StatusPill } from '../atoms/StatusPill'
import { PersonCell } from '../molecules/PersonCell'

export type AdminQuoteRow = {
  id: string
  number: string
  plan_id: string
  status: QuoteStatus
  /** In euros, as the API sends a decimal. */
  total: string
  valid_until: string
  country: string | null
  city: string | null
  start_date: string | null
  end_date: string | null
  client: { name: string | null; email: string } | null
}

type Props = { quotes: AdminQuoteRow[] }

/** Every client's quotes with their total, validity and status. Each opens its plan. */
export function AdminQuotesTable({ quotes }: Props) {
  const { t, i18n } = useTranslation('admin')
  return (
    <table className="w-full border-collapse border-t border-line text-sm">
      <caption className="sr-only">{t('activity.quotes.caption')}</caption>
      <thead>
        <tr className="text-xs tracking-widest text-muted uppercase">
          <th scope="col" className="px-2 py-4 text-start font-normal md:p-4">
            {t('activity.quotes.quote')}
          </th>
          <th scope="col" className="hidden p-4 text-start font-normal md:table-cell">
            {t('activity.quotes.trip')}
          </th>
          <th scope="col" className="px-2 py-4 text-end font-normal md:p-4">
            {t('activity.quotes.total')}
          </th>
          <th scope="col" className="hidden p-4 text-start font-normal md:table-cell">
            {t('activity.quotes.validUntil')}
          </th>
          <th scope="col" className="px-2 py-4 text-start font-normal md:p-4">
            {t('activity.quotes.status')}
          </th>
        </tr>
      </thead>
      <tbody>
        {quotes.map((quote) => (
          <tr key={quote.id} className="border-t border-line align-top">
            <th scope="row" className="px-2 py-4 text-start font-normal md:p-4">
              <span className="grid gap-1">
                <Link
                  to="/admin/activity/plans/$planId"
                  params={{ planId: quote.plan_id }}
                  className="inline-flex min-h-11 items-center font-semibold underline underline-offset-4"
                >
                  {quote.number}
                </Link>
                <PersonCell person={quote.client} fallback={t('activity.noClient')} />
              </span>
            </th>
            <td className="hidden p-4 md:table-cell">
              <span className="grid">
                <span>{placeOf(quote) ?? t('activity.noPlace')}</span>
                <small className="mt-1 text-xs text-muted">{datesOf(i18n.language, quote) ?? t('activity.noDates')}</small>
              </span>
            </td>
            <td className="px-2 py-4 text-end whitespace-nowrap md:p-4">{formatEuros(i18n.language, Number(quote.total))}</td>
            <td className="hidden p-4 md:table-cell">{formatShortDate(i18n.language, quote.valid_until)}</td>
            <td className="px-2 py-4 md:p-4">
              <StatusPill highlight={needsAttention(quote.status)}>{t(`activity.quoteStatus.${quote.status}`)}</StatusPill>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
