import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect, useId } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError, isUnauthenticated } from '../../../api/errors'
import { getMeQueryKey, getOfferOptions } from '../../../api/generated/@tanstack/react-query.gen'
import type { OfferDetailResponse } from '../../../api/generated/types.gen'
import { Chip } from '../../../components/atoms/Chip'
import { Eyebrow } from '../../../components/atoms/Eyebrow'
import { ErrorNote } from '../../../components/molecules/ErrorNote'
import { AppShell } from '../../../components/templates/AppShell'
import { localizeCountry } from '../../../lib/countries'
import { formatDayRange, formatEuros, formatMonthName } from '../../../lib/format'

export const Route = createFileRoute('/_authenticated/offers/$offerId')({
  component: OfferRoute,
})

/** One offer of the catalogue, as GET /offers/{id} gives it. Never the partner (ADR 0014). */
function OfferRoute() {
  const { offerId } = Route.useParams()
  const { t } = useTranslation('offer')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const offer = useQuery({ ...getOfferOptions({ path: { offer_id: offerId } }), retry: false })
  const signedOut = isUnauthenticated(offer.error)

  // The session ended while on the page: sign in again and come back (see the plan page).
  useEffect(() => {
    if (!signedOut) return
    queryClient.removeQueries({ queryKey: getMeQueryKey() })
    void navigate({ to: '/login', search: { redirect: `/offers/${encodeURIComponent(offerId)}` }, replace: true })
  }, [signedOut, queryClient, navigate, offerId])

  // 404: no such offer, or no longer listed. 422: the id is not even an offer id.
  const missing = offer.error instanceof ApiError && [404, 422].includes(offer.error.status)

  return (
    <AppShell tone="ivory">
      {/* Taller than the screen from the first paint: the scrollbar is there before the offer
          arrives, so it never pushes the page aside (on the left in RTL) when it loads. */}
      <div className="min-h-dvh">
        {offer.isPending || signedOut || (offer.isError && offer.isFetching) ? (
          <p className="px-5 pt-32 text-muted md:px-[8vw]">{t('loading')}</p>
        ) : missing ? (
          <p className="px-5 pt-32 md:px-[8vw]">{t('notFound')}</p>
        ) : offer.isError ? (
          <ErrorNote message={t('loadFailed')} onRetry={() => offer.refetch()} />
        ) : (
          <OfferPage offer={offer.data} />
        )}
      </div>
    </AppShell>
  )
}

function OfferPage({ offer }: { offer: OfferDetailResponse }) {
  const { t, i18n } = useTranslation('offer')
  const locale = i18n.language
  return (
    <main className="px-5 py-14 md:grid md:grid-cols-[1.2fr_0.8fr] md:items-start md:gap-16 md:px-[8vw] md:py-20">
      <div>
        <Eyebrow>{t('place', { city: offer.city, country: localizeCountry(locale, offer.country) })}</Eyebrow>
        {/* The partner's texts are shown as written, in French (lang: read with a French voice). */}
        <h1 lang="fr" className="mb-6 text-display-m">
          {offer.title}
        </h1>
        <Chip>{t(`kind.${offer.kind}`)}</Chip>
        {locale !== 'fr' && <p className="mt-4 mb-0 text-sm text-muted">{t('inFrench')}</p>}
        <p lang="fr" className="mt-8 max-w-[660px] font-serif text-lg leading-relaxed">
          {offer.description}
        </p>
        <OfferDetails offer={offer} locale={locale} />
      </div>
      <Price offer={offer} locale={locale} />
    </main>
  )
}

/** The price per person, labelled as indicative: the quote has the negotiated amount. */
function Price({ offer, locale }: { offer: OfferDetailResponse; locale: string }) {
  const { t } = useTranslation('offer')
  const labelId = useId()
  return (
    <aside aria-labelledby={labelId} className="mt-10 border-t border-ink pt-6 md:sticky md:top-37 md:mt-0">
      <p id={labelId} className="mb-2 text-xs font-semibold tracking-eyebrow uppercase">{t('price.label')}</p>
      {offer.price_eur !== null && offer.price_unit !== null ? (
        <p className="m-0">
          <span className="font-serif text-[43px] leading-tight">{formatEuros(locale, offer.price_eur)}</span>{' '}
          <span className="text-sm text-muted">{t(`price.unit.${offer.price_unit}`)}</span>
        </p>
      ) : (
        <p className="m-0 text-muted">{t('price.none')}</p>
      )}
      <p className="mt-4 text-sm leading-relaxed text-muted">{t('price.note')}</p>
    </aside>
  )
}

function OfferDetails({ offer, locale }: { offer: OfferDetailResponse; locale: string }) {
  const { t } = useTranslation('offer')
  const rows: { label: string; value: string; lang?: 'fr' }[] = [
    { label: t('details.dates'), value: formatDayRange(locale, offer.available_from, offer.available_to) },
    {
      label: t('details.persons'),
      value:
        offer.min_persons === offer.max_persons
          ? t('details.personsExact', { count: offer.max_persons })
          : t('details.personsRange', { min: offer.min_persons, max: offer.max_persons }),
    },
  ]
  if (offer.opening_months.length > 0) {
    rows.push({
      label: t('details.months'),
      value: new Intl.ListFormat(locale, { type: 'conjunction' }).format(
        offer.opening_months.map((month) => formatMonthName(locale, month)),
      ),
    })
  }
  for (const key of ['conditions', 'restrictions', 'cancellation'] as const) {
    const value = offer[key]
    if (value) rows.push({ label: t(`details.${key}`), value, lang: 'fr' })
  }
  if (offer.confirmation_delay_hours !== null) {
    rows.push({
      label: t('details.confirmation'),
      value:
        offer.confirmation_delay_hours === 0
          ? t('details.confirmationImmediate')
          : t('details.confirmationDelay', { count: offer.confirmation_delay_hours }),
    })
  }
  return (
    <section aria-label={t('details.label')} className="mt-12 max-w-[660px]">
      <dl className="m-0">
        {rows.map((row) => (
          <div key={row.label} className="grid gap-1 border-t border-line py-4 md:grid-cols-[180px_1fr] md:gap-6">
            <dt className="text-xs tracking-[0.15em] text-muted uppercase">{row.label}</dt>
            <dd lang={row.lang} className="m-0 text-sm leading-relaxed">
              {row.value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
