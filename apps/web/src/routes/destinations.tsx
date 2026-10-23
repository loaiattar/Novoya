import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { listReviewsOptions } from '../api/generated/@tanstack/react-query.gen'
import type { ReviewResponse } from '../api/generated/types.gen'
import { Eyebrow } from '../components/atoms/Eyebrow'
import { ErrorNote } from '../components/molecules/ErrorNote'
import { HomeLink } from '../components/molecules/HomeLink'
import { LanguageChoice } from '../components/organisms/LanguageChoice'
import { SiteFooter } from '../components/organisms/SiteFooter'
import { localizeCountry } from '../lib/countries'
import { formatDay } from '../lib/format'

export const Route = createFileRoute('/destinations')({
  component: DestinationsPage,
})

type Destination = { key: string; country: string; city: string; reviews: ReviewResponse[] }

/** The reviews by destination, in the order the API gives them (newest first). */
function byDestination(reviews: ReviewResponse[]): Destination[] {
  const groups = new Map<string, Destination>()
  for (const review of reviews) {
    const key = `${review.country}\u0000${review.city}`
    let group = groups.get(key)
    if (!group) {
      group = { key, country: review.country, city: review.city, reviews: [] }
      groups.set(key, group)
    }
    group.reviews.push(review)
  }
  return [...groups.values()]
}

/** Public: the published reviews of past travellers, by destination (ADR 0014). */
function DestinationsPage() {
  const { t } = useTranslation('destinations')
  const reviews = useQuery({ ...listReviewsOptions(), retry: false })

  return (
    <>
      <header className="flex h-18 items-center justify-between border-b border-line bg-paper px-5 md:h-22 md:px-[5vw]">
        <HomeLink />
        <LanguageChoice />
      </header>
      {/* At least a screen tall before the reviews arrive: the footer and the scrollbar stay put. */}
      <main className="min-h-dvh bg-ivory">
        <Link
          to="/"
          className="mx-5 mt-4 inline-flex min-h-11 items-center text-ink underline underline-offset-4 md:mx-[8vw] md:mt-6"
        >
          {t('back')}
        </Link>
        <section className="px-5 pt-10 pb-10 md:px-[8vw] md:pt-16 md:pb-16">
          <Eyebrow>{t('eyebrow')}</Eyebrow>
          <h1 className="m-0 text-display-m">
            {t('title')}
            <br />
            <em>{t('titleEnd')}</em>
          </h1>
          <p className="mt-8 max-w-[660px] font-serif text-lg leading-relaxed">{t('intro')}</p>
        </section>
        <div className="px-5 pb-20 md:px-[8vw]">
          {reviews.isPending || (reviews.isError && reviews.isFetching) ? (
            <p className="text-muted">{t('loading')}</p>
          ) : reviews.isError ? (
            <ErrorNote message={t('loadFailed')} onRetry={() => reviews.refetch()} />
          ) : reviews.data.length === 0 ? (
            <p className="text-muted">{t('empty')}</p>
          ) : (
            byDestination(reviews.data).map((destination) => (
              <DestinationReviews key={destination.key} destination={destination} />
            ))
          )}
        </div>
      </main>
      <SiteFooter />
    </>
  )
}

function DestinationReviews({ destination }: { destination: Destination }) {
  const { t, i18n } = useTranslation('destinations')
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className="border-t border-line py-10">
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={headingId} className="m-0 text-[34px] leading-tight">
          {t('place', { city: destination.city, country: localizeCountry(i18n.language, destination.country) })}
        </h2>
        <span className="text-sm text-muted">{t('count', { count: destination.reviews.length })}</span>
      </div>
      <ul className="m-0 grid list-none gap-6 p-0 md:grid-cols-2 md:gap-10">
        {destination.reviews.map((review) => (
          <li key={review.id}>
            <figure className="m-0 bg-paper p-6">
              <p className="mb-3 text-coral-text" role="img" aria-label={t('rating', { rating: review.rating })}>
                <span aria-hidden="true">{'★'.repeat(review.rating) + '☆'.repeat(5 - review.rating)}</span>
              </p>
              {/* Reviews are shown as the travellers wrote them, in French (lang: read with a French voice). */}
              <blockquote lang="fr" className="m-0 font-serif text-lg leading-relaxed">
                {review.text}
              </blockquote>
              <figcaption className="mt-4 flex flex-wrap gap-x-3 text-sm text-muted">
                {/* The author as published: "First name I." or "Voyageur anonyme", never translated. */}
                <span lang="fr" className="text-ink">
                  {review.author}
                </span>
                <time dateTime={review.reviewed_on}>{formatDay(i18n.language, review.reviewed_on)}</time>
                {i18n.language !== 'fr' && <span>{t('inFrench')}</span>}
              </figcaption>
            </figure>
          </li>
        ))}
      </ul>
    </section>
  )
}
