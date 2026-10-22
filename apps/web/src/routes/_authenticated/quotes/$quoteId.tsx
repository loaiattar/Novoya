import { createFileRoute } from '@tanstack/react-router'
import type { TFunction } from 'i18next'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../../api/errors'
import type { QuoteDetail } from '../../../api/generated/types.gen'
import { quotePdfUrl, useAnswerQuote, useQuote } from '../../../api/quotes'
import { Eyebrow } from '../../../components/atoms/Eyebrow'
import { DemoBanner } from '../../../components/molecules/DemoBanner'
import { ErrorNote } from '../../../components/molecules/ErrorNote'
import { QuoteDecision } from '../../../components/organisms/QuoteDecision'
import { QuoteSheet, type QuoteSheetLine } from '../../../components/organisms/QuoteSheet'
import { AppShell } from '../../../components/templates/AppShell'
import { DEMO_QUOTE_ID, getQuote } from '../../../fixtures/quotes'

export const Route = createFileRoute('/_authenticated/quotes/$quoteId')({
  component: QuoteRoute,
})

// The demo quote stays for the demo trips (/trips); every other id is read from the API.
function QuoteRoute() {
  const { quoteId } = Route.useParams()
  return quoteId === DEMO_QUOTE_ID ? <DemoQuotePage /> : <QuotePage quoteId={quoteId} />
}

function NotFound() {
  const { t } = useTranslation('quote')
  return <p className="px-5 pt-32 md:px-[8vw]">{t('notFound')}</p>
}

/** The quote the agent sent, as GET /quotes/{id} gives it, with the client's answer. */
function QuotePage({ quoteId }: { quoteId: string }) {
  const { t } = useTranslation('quote')
  const { quote, signedOut, missing } = useQuote(quoteId, `/quotes/${encodeURIComponent(quoteId)}`)

  return (
    <AppShell tone="ivory">
      {quote.isPending || signedOut ? (
        <p className="px-5 pt-32 text-muted md:px-[8vw]">{t('loading')}</p>
      ) : missing ? (
        <NotFound />
      ) : quote.data ? (
        <LiveQuote quote={quote.data} />
      ) : quote.isFetching ? (
        <p className="px-5 pt-32 text-muted md:px-[8vw]">{t('loading')}</p>
      ) : (
        <ErrorNote message={t('loadFailed')} onRetry={() => quote.refetch()} />
      )}
    </AppShell>
  )
}

function LiveQuote({ quote }: { quote: QuoteDetail }) {
  const { t } = useTranslation('quote')
  const answer = useAnswerQuote(quote.id)
  // A 409 means the quote expired or was answered meanwhile: the quote read again shows it.
  const failed = answer.isError && !(answer.error instanceof ApiError && answer.error.status === 409)
  const place = quote.city ?? quote.country
  return (
    <QuoteLayout
      number={quote.number}
      place={place}
      agentName={quote.agent_name}
      sheet={
        <QuoteSheet
          issuedAt={quote.sent_at}
          validUntil={quote.valid_until}
          startDate={quote.start_date}
          endDate={quote.end_date}
          travellers={quote.persons}
          lines={sheetLines(quote, t)}
          total={Number(quote.total)}
          budget={quote.budget_max === null ? null : Number(quote.budget_max)}
          pdfHref={quotePdfUrl(quote.id)}
        />
      }
      decision={
        <QuoteDecision
          status={quote.status}
          validUntil={quote.valid_until}
          decidedAt={quote.decided_at}
          comment={quote.client_comment}
          pending={answer.isPending}
          failed={failed}
          onDecide={(choice, comment) => answer.mutate({ answer: choice, comment })}
        />
      }
    />
  )
}

/** Each kept item on its day, then the extras, as the PDF lists them. */
function sheetLines(quote: QuoteDetail, t: TFunction<'quote'>): QuoteSheetLine[] {
  return [
    ...quote.items.map((item, index) => ({
      key: `item-${index}`,
      label: item.title ?? t('sheet.unavailable'),
      detail: t('sheet.itemDetail', { day: item.day, count: item.quantity }),
      amount: Number(item.price),
    })),
    ...quote.extras.map((extra, index) => ({
      key: `extra-${index}`,
      label: extra.label,
      detail: extra.unit || undefined,
      amount: extra.price === null ? null : Number(extra.price),
    })),
  ]
}

function QuoteLayout({
  number,
  place,
  agentName,
  sheet,
  decision,
}: {
  number: string
  place: string | null
  agentName: string | null
  sheet: ReactNode
  decision: ReactNode
}) {
  const { t } = useTranslation('quote')
  return (
    <main className="px-5 py-14 md:grid md:grid-cols-[0.8fr_1.2fr_0.65fr] md:items-start md:gap-10 md:px-[7vw] md:py-20">
      <div className="md:sticky md:top-37">
        <Eyebrow>{t('eyebrow', { id: number })}</Eyebrow>
        <h1 className="mb-6 text-[47px] leading-[0.98] md:text-[clamp(56px,5.6vw,82px)]">
          {t('titleStart')}
          {place && (
            <>
              <br />
              <em>{t('titleEnd', { place })}</em>
            </>
          )}
        </h1>
        <p className="text-muted">{agentName ? t('preparedBy', { name: agentName }) : t('preparedByAgency')}</p>
      </div>
      {sheet}
      {decision}
    </main>
  )
}

function DemoQuotePage() {
  const quote = getQuote(DEMO_QUOTE_ID)!
  return (
    <AppShell tone="ivory">
      <DemoBanner />
      <QuoteLayout
        number={quote.id}
        place={quote.destination}
        agentName={quote.agentName}
        sheet={
          <QuoteSheet
            issuedAt={quote.issuedAt}
            validUntil={quote.validUntil}
            startDate={quote.startDate}
            endDate={quote.endDate}
            travellers={quote.travellers}
            lines={quote.lines.map((line) => ({ key: line.label, ...line }))}
            total={quote.total}
            budget={quote.budget}
          />
        }
        decision={<QuoteDecision />}
      />
    </AppShell>
  )
}
