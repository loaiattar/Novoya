import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../../../../api/errors'
import { getAdminPlanOptions, listAdminQuotesOptions } from '../../../../../api/generated/@tanstack/react-query.gen'
import { client } from '../../../../../api/generated/client.gen'
import type { AdminPlan, AdminQuote } from '../../../../../api/generated/types.gen'
import { Eyebrow } from '../../../../../components/atoms/Eyebrow'
import { StatusPill } from '../../../../../components/atoms/StatusPill'
import { ErrorNote } from '../../../../../components/molecules/ErrorNote'
import { PersonCell } from '../../../../../components/molecules/PersonCell'
import { datesOf, needsAttention, placeOf } from '../../../../../domain/admin/activity'
import { formatEuros, formatShortDate } from '../../../../../lib/format'

// The guard is in ../../route.tsx: admins only.
export const Route = createFileRoute('/_authenticated/admin/activity/plans/$planId')({
  component: PlanPage,
})

/** One plan, read-only: what its agent sees (prices, partners, total and budget), and its quote. */
function PlanPage() {
  const { planId } = Route.useParams()
  const { t } = useTranslation('admin')
  const plan = useQuery(getAdminPlanOptions({ path: { plan_id: planId } }))
  const missing = plan.error instanceof ApiError && plan.error.status === 404

  return (
    <>
      <Link to="/admin/activity" search={{ tab: 'plans' }} className="text-sm underline underline-offset-4">
        {t('activity.plan.back')}
      </Link>
      {plan.isPending ? (
        <p className="py-6 text-muted">{t('activity.plan.loading')}</p>
      ) : missing ? (
        <p className="py-6">{t('activity.plan.notFound')}</p>
      ) : plan.isError ? (
        <ErrorNote message={t('activity.plan.loadFailed')} onRetry={() => plan.refetch()} />
      ) : (
        <PlanDetails view={plan.data} />
      )}
    </>
  )
}

function PlanDetails({ view }: { view: AdminPlan }) {
  const { t, i18n } = useTranslation('admin')
  const { plan } = view
  const locale = i18n.language
  const items = [...plan.items].sort((a, b) => a.day - b.day)
  const euros = (amount: string | null) => (amount === null ? null : formatEuros(locale, Number(amount)))

  return (
    <>
      <Eyebrow className="mt-6">{t('activity.plan.eyebrow')}</Eyebrow>
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <h1 className="m-0 text-display-s break-words">{placeOf(plan) ?? t('activity.noPlace')}</h1>
        <StatusPill highlight={needsAttention(plan.status)} className="self-start md:self-auto">
          {t(`activity.planStatus.${plan.status}`)}
        </StatusPill>
      </div>
      <p className="mt-3 max-w-[60ch]">{plan.summary}</p>
      <p className="mt-2 text-xs text-muted">{t('activity.plan.readOnly')}</p>

      <dl className="mt-8 grid gap-x-8 gap-y-5 border-t border-line pt-6 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <Fact label={t('activity.plan.client')}>
          <PersonCell person={view.client} fallback={t('activity.noClient')} />
        </Fact>
        <Fact label={t('activity.plan.agent')}>
          <PersonCell person={view.agent} fallback={t('activity.noAgent')} />
        </Fact>
        <Fact label={t('activity.plan.dates')}>{datesOf(locale, plan) ?? t('activity.noDates')}</Fact>
        <Fact label={t('activity.plan.travellers')}>{plan.persons ?? '—'}</Fact>
        <Fact label={t('activity.plan.budget')}>{euros(plan.budget_max) ?? t('activity.plan.noBudget')}</Fact>
        <Fact label={t('activity.plan.total')}>
          <span className="grid">
            <span className="font-serif text-[24px]">{euros(plan.total)}</span>
            {plan.over_budget && <small className="text-xs text-danger">{t('activity.plan.overBudget')}</small>}
          </span>
        </Fact>
      </dl>

      <h2 className="mt-12 mb-4 text-[28px]">{t('activity.plan.items')}</h2>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse border-t border-line text-sm">
          <caption className="sr-only">{t('activity.plan.itemsCaption')}</caption>
          <thead>
            <tr className="text-xs tracking-widest text-muted uppercase">
              <th scope="col" className="px-2 py-4 text-start font-normal md:p-4">
                {t('activity.plan.day')}
              </th>
              <th scope="col" className="px-2 py-4 text-start font-normal md:p-4">
                {t('activity.plan.item')}
              </th>
              <th scope="col" className="hidden p-4 text-start font-normal md:table-cell">
                {t('activity.plan.partner')}
              </th>
              <th scope="col" className="hidden p-4 text-end font-normal md:table-cell">
                {t('activity.plan.quantity')}
              </th>
              <th scope="col" className="px-2 py-4 text-end font-normal md:p-4">
                {t('activity.plan.price')}
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className={`border-t border-line align-top ${item.removed ? 'text-muted' : ''}`}>
                <td className="px-2 py-4 whitespace-nowrap md:p-4">{t('activity.plan.dayN', { day: item.day })}</td>
                <th scope="row" className="px-2 py-4 text-start font-normal md:p-4">
                  <span className="grid justify-items-start gap-1">
                    <span className={item.removed ? 'line-through' : 'font-semibold'}>
                      {item.title ?? t('activity.plan.unavailable')}
                    </span>
                    {item.removed && <StatusPill>{t('activity.plan.removed')}</StatusPill>}
                  </span>
                </th>
                <td className="hidden p-4 md:table-cell">
                  {item.partner_name ? (
                    <span className="grid">
                      <span>{item.partner_name}</span>
                      {item.partner_contact_email && (
                        <small className="mt-1 text-xs break-all text-muted">{item.partner_contact_email}</small>
                      )}
                    </span>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </td>
                <td className="hidden p-4 text-end md:table-cell">{item.quantity}</td>
                <td className="px-2 py-4 text-end whitespace-nowrap md:p-4">
                  {euros(item.negotiated_price) ?? <span className="text-muted">{t('activity.plan.noPrice')}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {plan.extras.length > 0 && (
        <>
          <h2 className="mt-12 mb-4 text-[28px]">{t('activity.plan.extras')}</h2>
          <ul className="m-0 grid list-none gap-0 border-t border-line p-0 text-sm">
            {plan.extras.map((extra) => (
              <li key={extra.extra_id} className="flex justify-between gap-4 border-b border-line px-2 py-4 md:px-4">
                <span>
                  {extra.label}
                  {extra.unit && <small className="ms-2 text-xs text-muted">{extra.unit}</small>}
                </span>
                <span className="whitespace-nowrap">
                  {extra.pricing === 'included'
                    ? t('activity.plan.included')
                    : (euros(extra.price_eur) ?? <span className="text-muted">{t('activity.plan.onQuote')}</span>)}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      <PlanQuote planId={plan.id} />
    </>
  )
}

/** The plan's quote, if one was sent: number, status, validity, total and its PDF. */
function PlanQuote({ planId }: { planId: string }) {
  const { t } = useTranslation('admin')
  const quotes = useQuery(listAdminQuotesOptions({ query: { plan_id: planId } }))
  const [quote] = quotes.data ?? []

  return (
    <section aria-labelledby="plan-quote" className="mt-12">
      <h2 id="plan-quote" className="mb-4 text-[28px]">
        {t('activity.plan.quote')}
      </h2>
      {quotes.isPending ? (
        <p className="text-muted">{t('activity.loading')}</p>
      ) : quotes.isError ? (
        <ErrorNote message={t('activity.plan.quoteLoadFailed')} onRetry={() => quotes.refetch()} />
      ) : !quote ? (
        <p className="text-muted">{t('activity.plan.noQuote')}</p>
      ) : (
        <QuoteCard quote={quote} />
      )}
    </section>
  )
}

function QuoteCard({ quote }: { quote: AdminQuote }) {
  const { t, i18n } = useTranslation('admin')
  const locale = i18n.language
  return (
    <div className="flex flex-col gap-4 border border-line bg-ivory p-5 md:flex-row md:items-center md:justify-between">
      <div className="grid gap-1 text-sm">
        <span className="flex flex-wrap items-center gap-3">
          <b className="font-semibold">{quote.number}</b>
          <StatusPill highlight={needsAttention(quote.status)}>{t(`activity.quoteStatus.${quote.status}`)}</StatusPill>
        </span>
        <small className="text-xs text-muted">
          {t('activity.plan.sentOn', { date: formatShortDate(locale, quote.sent_at) })} ·{' '}
          {t('activity.plan.validUntil', { date: formatShortDate(locale, quote.valid_until) })}
        </small>
      </div>
      <div className="flex flex-wrap items-center gap-5">
        <span className="font-serif text-[24px]">{formatEuros(locale, Number(quote.total))}</span>
        <a
          href={`${client.getConfig().baseUrl}/quotes/${quote.id}/pdf`}
          className="inline-flex min-h-11 items-center text-sm underline underline-offset-4"
        >
          {t('activity.plan.pdf')}
        </a>
      </div>
    </div>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid content-start gap-1.5">
      <dt className="text-xs tracking-widest text-muted uppercase">{label}</dt>
      <dd className="m-0">{children}</dd>
    </div>
  )
}
