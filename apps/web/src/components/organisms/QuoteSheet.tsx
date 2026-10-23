import { useTranslation } from 'react-i18next'

import { formatAgencyDay, formatDayRange, formatEuros } from '@/lib/format'

import { Logo } from '../atoms/Logo'

export type QuoteSheetLine = {
  key: string
  label: string
  /** Under the label, smaller: the day and quantity of an item, the unit of an extra. */
  detail?: string
  /** In euros. null: included. */
  amount: number | null
}

type Props = {
  /** ISO date-times; shown as the agency's day, like the PDF. */
  issuedAt: string
  validUntil: string
  /** ISO dates; null when the trip is no longer known. */
  startDate: string | null
  endDate: string | null
  travellers: number | null
  lines: QuoteSheetLine[]
  total: number
  budget: number | null
  /** Where the PDF downloads. Without it the link is disabled and says why. */
  pdfHref?: string
}

const DAY_MS = 24 * 60 * 60 * 1000

/** The agency's offer, laid out like a printed quote. Prices come from the agent, never the AI. */
export function QuoteSheet({ issuedAt, validUntil, startDate, endDate, travellers, lines, total, budget, pdfHref }: Props) {
  const { t, i18n } = useTranslation('quote')
  const locale = i18n.language
  const nights = startDate && endDate ? Math.round((Date.parse(endDate) - Date.parse(startDate)) / DAY_MS) : null
  return (
    <section aria-label={t('sheet.label')} className="my-9 bg-white px-4.5 py-6 shadow-card md:my-0 md:p-11">
      <div className="flex justify-between gap-4">
        <div className="grid">
          <Logo />
          <small className="mt-1 text-xs text-muted">{t('sheet.agency')}</small>
        </div>
        <div className="grid text-right text-xs">
          <b>{t('sheet.validUntil', { date: formatAgencyDay(locale, validUntil) })}</b>
          <span className="mt-1.5 text-muted">{t('sheet.issued', { date: formatAgencyDay(locale, issuedAt) })}</span>
        </div>
      </div>
      <ul className="my-8 flex flex-col gap-2 border-y border-line py-5 text-xs md:flex-row md:justify-between">
        {startDate && endDate && <li>{formatDayRange(locale, startDate, endDate)}</li>}
        {travellers !== null && <li>{t('sheet.travellers', { count: travellers })}</li>}
        {nights !== null && (
          <li>
            {t('sheet.length', {
              days: t('sheet.days', { count: nights + 1 }),
              nights: t('sheet.nights', { count: nights }),
            })}
          </li>
        )}
      </ul>
      <dl>
        {lines.map((line) => (
          <div key={line.key} className="flex justify-between gap-4 border-b border-line py-4 text-sm">
            <dt>
              {line.label}
              {line.detail && <span className="mt-1 block text-xs text-muted">{line.detail}</span>}
            </dt>
            <dd className="m-0 shrink-0 font-semibold">
              {line.amount === null ? t('sheet.included') : formatEuros(locale, line.amount)}
            </dd>
          </div>
        ))}
        <div className="flex justify-between py-7 font-serif text-[25px]">
          <dt>{t('sheet.total')}</dt>
          <dd className="m-0">{formatEuros(locale, total)}</dd>
        </div>
      </dl>
      {budget !== null && (
        <p className="m-0 bg-ivory p-3 text-center text-xs">
          {t('sheet.budget', { amount: formatEuros(locale, budget) })}
        </p>
      )}
      <p className="mt-4 text-center text-xs text-muted">
        {pdfHref ? (
          <a href={pdfHref} download className="inline-flex min-h-11 items-center underline underline-offset-4">
            {t('sheet.download')}
          </a>
        ) : (
          <>
            <button type="button" disabled className="min-h-11 underline underline-offset-4 disabled:cursor-not-allowed">
              {t('sheet.download')}
            </button>
            <br />
            {t('sheet.pdfDemo')}
          </>
        )}
      </p>
    </section>
  )
}
