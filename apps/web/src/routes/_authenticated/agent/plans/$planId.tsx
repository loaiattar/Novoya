import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { queueOptions, useAgentPlan, usePlanQuote } from '../../../../api/agentPlans'
import { ApiError } from '../../../../api/errors'
import { client } from '../../../../api/generated/client.gen'
import {
  getAgentPlanQueryKey,
  getPlanQuoteQueryKey,
  sendQuoteMutation,
  setPlanExtraMutation,
  setPlanItemMutation,
} from '../../../../api/generated/@tanstack/react-query.gen'
import type { AgentPlan, AgentPlanExtra, AgentPlanItem, PlanQuote } from '../../../../api/generated/types.gen'
import { Button } from '../../../../components/atoms/Button'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { StatusPill } from '../../../../components/atoms/StatusPill'
import { ErrorNote } from '../../../../components/molecules/ErrorNote'
import { PriceField } from '../../../../components/molecules/PriceField'
import { ChatThread } from '../../../../components/organisms/AdvisorChat'
import { SendQuoteDialog } from '../../../../components/organisms/SendQuoteDialog'
import { groupByDay } from '../../../../domain/plan/days'
import { missingPrices } from '../../../../domain/plan/quoteReadiness'
import { formatAgencyDay, formatDayRange, formatEuros } from '../../../../lib/format'

export const Route = createFileRoute('/_authenticated/agent/plans/$planId')({
  component: AgentPlanRoute,
})

const QUOTE_VALID_DAYS = 7 // as the API's quote (quoting/domain/quote.py): sent_at + 7 days, its Paris day
const DAY_MS = 24 * 60 * 60 * 1000

function AgentPlanRoute() {
  const { t } = useTranslation('agent')
  const { planId } = Route.useParams()
  const { plan, signedOut, missing } = useAgentPlan(planId, `/agent/plans/${encodeURIComponent(planId)}`)

  // A screen tall, like the plan that replaces it, so the footer does not jump.
  if (plan.isPending || signedOut) return <p className="min-h-dvh text-muted">{t('plan.loading')}</p>
  if (missing) return <p>{t('plan.notFound')}</p>
  // Kept when reading it again in the background fails: what is on screen is still right.
  if (plan.data) return <PlanView plan={plan.data} />
  if (plan.isFetching) return <p className="min-h-dvh text-muted">{t('plan.loading')}</p>
  return <ErrorNote message={t('plan.loadFailed')} onRetry={() => plan.refetch()} />
}

/** What the API says about a failed save, for the line it belongs to. */
function useSaveErrorText() {
  const { t } = useTranslation('agent')
  return (error: unknown) =>
    error instanceof ApiError && error.status === 422 ? t('plan.priceNotSaved') : t('plan.changeFailed')
}

/** The plan as its agent works on it: partners to call, prices, total vs budget, the quote. */
function PlanView({ plan }: { plan: AgentPlan }) {
  const { t, i18n } = useTranslation('agent')
  const locale = i18n.language
  const queryClient = useQueryClient()
  const planKey = getAgentPlanQueryKey({ path: { plan_id: plan.id } })
  const negotiating = plan.status === 'negotiating'
  const place = [plan.city, plan.country].filter(Boolean).join(', ')

  // Each save answers with the whole plan: its total and readiness follow at once.
  const onSaved = (saved: AgentPlan) => queryClient.setQueryData(planKey, saved)
  const onFailed = (error: unknown) => {
    // 409: the plan is no longer negotiating (quoted in another tab). Read it again.
    if (error instanceof ApiError && error.status === 409) void queryClient.invalidateQueries({ queryKey: planKey })
  }
  // One scope for every save on the plan: they run one after the other, so the last answer
  // always holds the earlier saves, and a slow one cannot put an older price back on screen.
  const scope = { id: `agent-plan-${plan.id}` }
  const setItem = useMutation({ ...setPlanItemMutation(), scope, onSuccess: onSaved, onError: onFailed })
  const setExtra = useMutation({ ...setPlanExtraMutation(), scope, onSuccess: onSaved, onError: onFailed })

  return (
    <article className="grid gap-12">
      <header className="grid gap-4">
        <Link to="/agent" className="-my-3 inline-flex min-h-11 items-center justify-self-start text-sm text-muted">
          {t('plan.back')}
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          {place && <Eyebrow>{place}</Eyebrow>}
          <StatusPill highlight={negotiating}>{t(`status.${plan.status}`)}</StatusPill>
        </div>
        <p className="m-0 max-w-[660px] font-serif text-2xl leading-snug md:text-3xl">{plan.summary}</p>
        {plan.start_date && plan.end_date && (
          <p className="m-0 text-sm text-muted">
            {t('request.datesTravellers', {
              dates: formatDayRange(locale, plan.start_date, plan.end_date),
              count: plan.persons ?? 1,
            })}
          </p>
        )}
        {plan.wish_text && (
          <blockquote className="m-0 max-w-[660px] border-s-2 border-line ps-4 text-sm text-muted">
            <span className="sr-only">{t('plan.wish')}: </span>“{plan.wish_text}”
          </blockquote>
        )}
      </header>

      {groupByDay(plan.items).map(({ day, items }) => (
        <section key={day} className="grid gap-2">
          <h2 className="m-0 text-xs font-semibold tracking-[0.15em] text-muted uppercase">{t('plan.day', { day })}</h2>
          {items.map((item) => (
            <ItemLine
              key={item.id}
              item={item}
              editable={negotiating}
              onPrice={(amount) =>
                setItem.mutateAsync({ path: { plan_id: plan.id, item_id: item.id }, body: { negotiated_price: amount } })
              }
              onRemoved={(removed) =>
                setItem.mutateAsync({ path: { plan_id: plan.id, item_id: item.id }, body: { removed } })
              }
            />
          ))}
        </section>
      ))}

      {plan.extras.length > 0 && (
        <section className="grid gap-2">
          <h2 className="m-0 text-xs font-semibold tracking-[0.15em] text-muted uppercase">{t('plan.extras')}</h2>
          {plan.extras.map((extra) => (
            <ExtraLine
              key={extra.extra_id}
              extra={extra}
              editable={negotiating}
              onPrice={(amount) =>
                setExtra.mutateAsync({ path: { plan_id: plan.id, extra_id: extra.extra_id }, body: { price_eur: amount } })
              }
            />
          ))}
        </section>
      )}

      <section className="grid gap-2 border-t border-line pt-6">
        <dl className="m-0 grid grid-cols-[auto_1fr] items-baseline gap-x-6 gap-y-2">
          <dt className="text-sm text-muted">{t('plan.total')}</dt>
          <dd className="m-0 font-serif text-3xl">{formatEuros(locale, Number(plan.total))}</dd>
          <dt className="text-sm text-muted">{t('plan.budget')}</dt>
          <dd className="m-0">
            {plan.budget_max === null ? t('request.noBudget') : formatEuros(locale, Number(plan.budget_max))}
          </dd>
        </dl>
        {plan.over_budget && (
          <p role="status" className="m-0 text-sm text-danger">
            {t('plan.overBudget')}
          </p>
        )}
      </section>

      <QuoteSection plan={plan} />

      <ClientChat wishId={plan.wish_id} />
    </article>
  )
}

type ItemProps = {
  item: AgentPlanItem
  editable: boolean
  onPrice: (amount: string) => Promise<unknown>
  onRemoved: (removed: boolean) => Promise<unknown>
}

function ItemLine({ item, editable, onPrice, onRemoved }: ItemProps) {
  const { t, i18n } = useTranslation('agent')
  const errorText = useSaveErrorText()
  const [error, setError] = useState<string | null>(null)
  const title = item.title ?? ''
  const toggle = () => {
    setError(null)
    onRemoved(!item.removed).catch((reason: unknown) => setError(errorText(reason)))
  }
  return (
    <div className="grid gap-3 border-b border-line py-4 md:grid-cols-[1fr_auto] md:items-center">
      <div className={item.removed ? 'text-muted' : undefined}>
        <h3 className={`m-0 font-serif text-xl tracking-normal ${item.removed ? 'line-through' : ''}`}>{title}</h3>
        {item.partner_name && <p className="m-0 mt-1 text-sm">{item.partner_name}</p>}
        <p className="m-0 flex flex-wrap gap-x-4 text-sm text-muted">
          {item.partner_contact_phone && (
            <a href={`tel:${item.partner_contact_phone.replace(/\s/g, '')}`} className="min-h-11 content-center">
              {item.partner_contact_phone}
            </a>
          )}
          {item.partner_contact_email && (
            <a href={`mailto:${item.partner_contact_email}`} className="min-h-11 content-center break-all">
              {item.partner_contact_email}
            </a>
          )}
        </p>
      </div>
      <div className="flex flex-wrap items-start gap-3 md:justify-end">
        {item.removed ? (
          <span className="text-sm text-muted">{t('plan.removed')}</span>
        ) : editable ? (
          <PriceField
            label={t('plan.priceOf', { title })}
            value={item.negotiated_price}
            onSave={onPrice}
            errorText={errorText}
          />
        ) : (
          <span className="font-serif">
            {item.negotiated_price === null ? t('plan.noPrice') : formatEuros(i18n.language, Number(item.negotiated_price))}
          </span>
        )}
        {editable && (
          <Button variant="outline" onClick={toggle}>
            {item.removed ? t('plan.putBack', { title }) : t('plan.remove', { title })}
          </Button>
        )}
      </div>
      {error && (
        <p role="alert" className="m-0 text-xs text-danger md:col-span-2">
          {error}
        </p>
      )}
    </div>
  )
}

function ExtraLine({
  extra,
  editable,
  onPrice,
}: {
  extra: AgentPlanExtra
  editable: boolean
  onPrice: (amount: string) => Promise<unknown>
}) {
  const { t, i18n } = useTranslation('agent')
  const errorText = useSaveErrorText()
  const [error, setError] = useState<string | null>(null)
  const included = extra.pricing === 'included'
  const unconfirmed = extra.needs_quantity_check && !extra.confirmed
  // The supplement already has its price: once the partner confirms the quantity, keep it.
  const confirm = () => {
    if (extra.price_eur === null) return
    setError(null)
    onPrice(extra.price_eur).catch((reason: unknown) => setError(errorText(reason)))
  }
  return (
    <div className="grid gap-3 border-b border-line py-4 md:grid-cols-[1fr_auto] md:items-center">
      <div>
        <h3 className="m-0 font-serif text-lg tracking-normal">{extra.label}</h3>
        {unconfirmed && (
          <p className="m-0 mt-1 text-sm text-muted">{t('plan.checkQuantity')}</p>
        )}
      </div>
      <div className="md:justify-self-end">
        {included ? (
          <span className="text-sm text-muted">{t('plan.included')}</span>
        ) : editable ? (
          <span className="flex flex-wrap items-start gap-3">
            <PriceField
              label={t('plan.priceOf', { title: extra.label })}
              value={extra.price_eur}
              onSave={onPrice}
              errorText={errorText}
              unconfirmed={unconfirmed}
            />
            {unconfirmed && extra.price_eur !== null && (
              <Button variant="outline" onClick={confirm}>
                {t('plan.confirm', { title: extra.label })}
              </Button>
            )}
          </span>
        ) : (
          <span className="font-serif">
            {extra.price_eur === null ? t('plan.noPrice') : formatEuros(i18n.language, Number(extra.price_eur))}
          </span>
        )}
      </div>
      {error && (
        <p role="alert" className="m-0 text-xs text-danger md:col-span-2">
          {error}
        </p>
      )}
    </div>
  )
}

/** Sending the quote while negotiating; once sent, its number and its PDF. */
function QuoteSection({ plan }: { plan: AgentPlan }) {
  const { t, i18n } = useTranslation('agent')
  const locale = i18n.language
  const queryClient = useQueryClient()
  const planKey = getAgentPlanQueryKey({ path: { plan_id: plan.id } })
  const quoteKey = getPlanQuoteQueryKey({ path: { plan_id: plan.id } })
  const negotiating = plan.status === 'negotiating'
  const quote = usePlanQuote(plan.id, !negotiating && plan.status !== 'requested', plan.status)
  // The validity shown in the dialog, set when it opens; null while it is closed.
  const [asking, setAsking] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const missing = missingPrices(plan)

  const send = useMutation({
    ...sendQuoteMutation(),
    onSuccess: (sent) => {
      // Just sent: open, with no answer yet.
      const { email_sent: _emailSent, ...fields } = sent
      const fresh: PlanQuote = { ...fields, status: 'open', decided_at: null, client_comment: null }
      queryClient.setQueryData(quoteKey, fresh)
      queryClient.setQueryData(planKey, { ...plan, status: 'quoted' as const })
      void queryClient.invalidateQueries({ queryKey: planKey })
      void queryClient.invalidateQueries({ queryKey: queueOptions('in_progress').queryKey })
      void queryClient.invalidateQueries({ queryKey: queueOptions('decided').queryKey })
    },
    onError: (reason) => {
      // 422: a line lost its price meanwhile. 409: already sent, or no longer negotiating.
      // Either way the plan is read again; the prices on screen come from it, nothing is lost.
      const status = reason instanceof ApiError ? reason.status : 0
      setError(
        status === 422 && reason instanceof ApiError && reason.code === 'plan_not_ready'
          ? t('quote.notReady')
          : status === 409
            ? t('quote.alreadySent')
            : t('quote.failed'),
      )
      if (status === 422 || status === 409) void queryClient.invalidateQueries({ queryKey: planKey })
    },
  })

  const confirm = () => {
    setAsking(null)
    if (send.isPending) return
    setError(null)
    send.mutate({ path: { plan_id: plan.id } })
  }

  const errorNote = error && (
    <p role="alert" className="m-0 text-sm text-danger">
      {error}
    </p>
  )

  if (!negotiating) {
    return (
      <section className="grid gap-3">
        {errorNote}
        {quote.isError && !quote.data && (
          <ErrorNote message={t('quote.loadFailed')} onRetry={() => quote.refetch()} />
        )}
        {quote.data && (
          <>
            <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
              <dt className="text-muted">{t('quote.number')}</dt>
              <dd className="m-0 font-semibold">{quote.data.number}</dd>
            </dl>
            <p className="m-0 text-sm text-muted">
              {t('quote.sentOn', { date: formatAgencyDay(locale, quote.data.sent_at) })} ·{' '}
              {t('quote.validUntil', { date: formatAgencyDay(locale, quote.data.valid_until) })}
            </p>
            <ClientAnswer quote={quote.data} />
            <Button asChild variant="coral" className="w-full md:w-fit">
              <a href={`${client.getConfig().baseUrl}/quotes/${quote.data.id}/pdf`} download>
                {t('quote.download')}
              </a>
            </Button>
          </>
        )}
      </section>
    )
  }

  return (
    <section className="grid gap-4">
      {missing.length > 0 && (
        <div className="grid gap-2">
          <p id="still-to-price" className="m-0 text-sm font-semibold">
            {t('quote.missing')}
          </p>
          <ul aria-labelledby="still-to-price" className="m-0 grid gap-1 ps-5 text-sm text-muted">
            {missing.map((line) => (
              <li key={`${line.kind}-${line.id}`}>
                {line.kind === 'item' ? t('quote.missingItem', { day: line.day, title: line.title ?? '' }) : line.label}
              </li>
            ))}
          </ul>
        </div>
      )}
      {errorNote}
      <Button
        variant="coral"
        size="lg"
        className="w-full md:w-fit"
        disabled={!plan.ready_to_quote || missing.length > 0 || send.isPending}
        onClick={() => setAsking(new Date(Date.now() + QUOTE_VALID_DAYS * DAY_MS).toISOString())}
      >
        {t('quote.send')}
      </Button>
      <SendQuoteDialog
        total={plan.total}
        budget={plan.budget_max}
        validUntil={asking}
        onConfirm={confirm}
        onCancel={() => setAsking(null)}
      />
    </section>
  )
}

/** Where the sent quote stands: waiting, expired, or the client's answer with their comment. */
function ClientAnswer({ quote }: { quote: PlanQuote }) {
  const { t, i18n } = useTranslation('agent')
  const day = (iso: string | null) => (iso ? formatAgencyDay(i18n.language, iso) : '')
  const answered = quote.status === 'accepted' || quote.status === 'rejected'
  return (
    <div role="status" className="grid gap-2 border-s-2 border-line ps-4 text-sm">
      <p className="m-0 font-semibold">
        {quote.status === 'accepted'
          ? t('quote.answer.accepted', { date: day(quote.decided_at) })
          : quote.status === 'rejected'
            ? t('quote.answer.rejected', { date: day(quote.decided_at) })
            : quote.status === 'expired'
              ? t('quote.answer.expired', { date: day(quote.valid_until) })
              : quote.status === 'open'
                ? t('quote.answer.open')
                : null}
      </p>
      {answered && (
        <p className="m-0">
          <span className="text-muted">{t('quote.answer.comment')}</span>{' '}
          {quote.client_comment ? <q>{quote.client_comment}</q> : t('quote.answer.noComment')}
        </p>
      )}
    </div>
  )
}

/** The advisor chat of the plan's wish (#169): the agent answers the client here. */
function ClientChat({ wishId }: { wishId: string }) {
  const { t } = useTranslation('chat')
  return (
    <section aria-labelledby="client-chat-title" className="grid gap-3 border-t border-line pt-6">
      <div>
        <h2 id="client-chat-title" className="m-0 text-xs font-semibold tracking-[0.15em] text-muted uppercase">
          {t('agentTitle')}
        </h2>
        <p className="m-0 mt-1 text-sm text-muted">{t('agentIntro')}</p>
      </div>
      <div className="flex max-h-[480px] flex-col rounded-2xl border border-line bg-white">
        <ChatThread wishId={wishId} side="agency" />
      </div>
    </section>
  )
}
