import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { AdvisorServiceResponse } from '../../api/generated'
import { listAdvisorsOptions, listReviewsOptions } from '../../api/generated/@tanstack/react-query.gen'
import { formatDay } from '../../lib/format'
import { initials } from '../../lib/initials'
import { Eyebrow } from '../atoms/Eyebrow'

const display = 'm-0 text-display-l'
const sectionTitle = 'm-0 text-display-l'

/** How the agency works, in two lines and a sentence. */
export function Manifesto() {
  const { t } = useTranslation('home')
  return (
    <section className="bg-ivory px-6 py-[90px] md:px-[8vw] md:py-[130px]">
      <Eyebrow>{t('manifesto.eyebrow')}</Eyebrow>
      <div className="lg:grid lg:grid-cols-[1.4fr_0.6fr] lg:items-end lg:gap-[10vw]">
        <h2 className={display}>
          {t('manifesto.titleStart')}
          <br />
          {t('manifesto.titleEnd')}
        </h2>
        <p className="mt-8 mb-2.5 max-w-[560px] text-[19px] leading-relaxed text-muted lg:mt-0">{t('manifesto.lead')}</p>
      </div>
    </section>
  )
}

/** Three trips to take a step aside: a heading, then the trip cards given as children. */
export function PopularTrips({ children }: { children: ReactNode }) {
  const { t } = useTranslation('home')
  return (
    <section id="voyages" aria-labelledby="voyages-title" className="bg-ivory px-6 pb-[90px] md:px-[5vw] md:pb-[140px]">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-6 md:mx-[3vw] md:mb-[60px]">
        <div>
          <Eyebrow>{t('popular.eyebrow')}</Eyebrow>
          <h2 id="voyages-title" className={sectionTitle}>
            {t('popular.title')}
          </h2>
        </div>
        <Link
          to="/destinations"
          className="inline-flex min-h-11 items-center gap-2 border-b border-ink font-semibold text-ink no-underline"
        >
          {t('popular.all')} <span aria-hidden="true">↗</span>
        </Link>
      </div>
      <div className="-mr-6 flex snap-x snap-mandatory gap-6 overflow-x-auto md:[&>*]:min-w-[44vw] lg:mr-0 lg:grid lg:grid-cols-3 lg:overflow-visible [&>*]:min-w-[84vw] [&>*]:snap-start lg:[&>*]:min-w-0">
        {children}
      </div>
    </section>
  )
}

const STEPS = [
  ['01', 'wish'],
  ['02', 'preview'],
  ['03', 'offer'],
] as const

/** From the wish to the offer: three steps, on navy. */
export function Method() {
  const { t } = useTranslation('home')
  return (
    <section
      id="methode"
      className="bg-ink px-6 py-[90px] text-ivory md:grid md:grid-cols-[0.8fr_1.2fr] md:gap-[12vw] md:px-[8vw] md:py-[120px]"
    >
      <div>
        <Eyebrow light>{t('method.eyebrow')}</Eyebrow>
        <h2 className="m-0 text-display-l">
          {t('method.titleStart')}
          <br />
          {t('method.titleEnd')}
        </h2>
      </div>
      <ol className="mt-[55px] list-none p-0 md:mt-0">
        {STEPS.map(([number, step]) => (
          <li key={number} className="grid grid-cols-[56px_1fr] border-t border-ivory/60 py-[25px] md:grid-cols-[70px_1fr]">
            <span className="font-mono text-xs font-medium text-coral">{number}</span>
            <div>
              <h3 className="m-0 font-serif text-[25px] leading-tight font-semibold">
                {t(`method.steps.${step}.title`)}
              </h3>
              <p className="mt-1.5 mb-0 text-ivory/90">{t(`method.steps.${step}.copy`)}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

/** The four newest reviews, on sky blue. Hidden while they load or when there are none. */
export function Reviews() {
  const { t, i18n } = useTranslation('home')
  const reviews = useQuery({ ...listReviewsOptions(), retry: false })
  // Never let a section break the landing page: anything but a list shows nothing.
  const latest = Array.isArray(reviews.data) ? reviews.data.slice(0, 4) : []
  if (latest.length === 0) return null
  return (
    <section aria-labelledby="reviews-title" className="bg-sky px-6 py-[90px] md:px-[5vw] md:py-[130px]">
      <div className="mb-10 md:mx-[3vw] md:mb-[60px]">
        <Eyebrow>{t('reviews.eyebrow')}</Eyebrow>
        <h2 id="reviews-title" className={sectionTitle}>
          {t('reviews.title')}
        </h2>
      </div>
      <ul className="m-0 grid list-none gap-6 p-0 md:mx-[3vw] md:grid-cols-2">
        {latest.map((review) => (
          <li key={review.id}>
            <figure className="m-0 flex h-full min-h-[300px] flex-col rounded-2xl bg-ivory p-7 md:min-h-[360px] md:p-[35px]">
              <div className="flex justify-between font-mono text-xs font-medium tracking-[0.08em] text-muted uppercase">
                <span role="img" aria-label={t('reviews.rating', { rating: review.rating })}>
                  <span aria-hidden="true">{review.rating} / 5</span>
                </span>
                <time dateTime={review.reviewed_on}>{formatDay(i18n.language, review.reviewed_on)}</time>
              </div>
              {/* Reviews are shown as the travellers wrote them, in French. */}
              <blockquote
                lang="fr"
                className="mx-0 mt-10 mb-7 flex-1 font-serif text-xl leading-[1.3] font-semibold tracking-[-0.02em] md:mt-[45px] md:text-2xl"
              >
                « {review.text} »
              </blockquote>
              <figcaption lang="fr" className="text-sm font-bold">
                {review.author}
              </figcaption>
            </figure>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** A service in the visitor's language, else in the other one: the admin may give only one. */
function serviceLabel(service: AdvisorServiceResponse, language: string): { text: string; lang?: 'fr' | 'en' } {
  const own = language.startsWith('fr') ? service.fr : service.en
  if (own) return { text: own }
  return service.fr ? { text: service.fr, lang: 'fr' } : { text: service.en ?? '', lang: 'en' }
}

/** The agents an admin chose to show, on navy. Hidden while they load or when there are none. */
export function Advisors() {
  const { t, i18n } = useTranslation('home')
  const advisors = useQuery({ ...listAdvisorsOptions(), retry: false })
  // Never let a section break the landing page: anything but a list shows nothing.
  const shown = Array.isArray(advisors.data) ? advisors.data : []
  if (shown.length === 0) return null
  return (
    <section
      id="equipe"
      aria-labelledby="advisors-title"
      className="bg-ink px-6 py-[90px] text-ivory md:px-[5vw] md:py-[130px]"
    >
      <div className="mb-10 md:mx-[3vw] md:mb-[60px]">
        <Eyebrow light>{t('advisors.eyebrow')}</Eyebrow>
        <h2 id="advisors-title" className={sectionTitle}>
          {t('advisors.title')}
        </h2>
      </div>
      <ul className="m-0 grid list-none gap-6 p-0 md:mx-[3vw] md:grid-cols-2 lg:grid-cols-3">
        {shown.map((advisor) => (
          <li
            key={advisor.id}
            className="flex flex-col rounded-2xl border border-ivory/25 p-7 md:min-h-[360px] md:p-[35px]"
          >
            <span
              aria-hidden="true"
              className="grid size-[72px] place-items-center rounded-full bg-ivory font-serif text-2xl font-extrabold text-ink"
            >
              {initials(advisor.name)}
            </span>
            <div className="mt-10 md:mt-auto md:pt-12">
              <p className="mb-3 font-mono text-xs font-medium tracking-eyebrow text-sky uppercase">
                {advisor.title ?? t('advisors.defaultTitle')}
              </p>
              <h3 className="m-0 font-serif text-[32px] leading-[1.04] font-extrabold tracking-display break-words">
                {advisor.name}
              </h3>
              {advisor.summary && <p className="mt-3 mb-0 text-ivory/80">{advisor.summary}</p>}
              {advisor.services.length > 0 && (
                <ul aria-label={t('advisors.services')} className="mt-5 flex list-none flex-wrap gap-2 p-0">
                  {advisor.services.map((service, index) => {
                    const label = serviceLabel(service, i18n.language)
                    return (
                      <li
                        key={index}
                        lang={label.lang}
                        className="rounded-full border border-ivory/35 px-3 py-1 text-sm"
                      >
                        {label.text}
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** The last call to action, on yellow. */
export function Closing({ action }: { action: ReactNode }) {
  const { t } = useTranslation('home')
  return (
    <section className="bg-coral px-6 py-[90px] text-ink md:px-[8vw] md:py-[125px]">
      <Eyebrow>{t('closing.eyebrow')}</Eyebrow>
      <h2 className={`${display} mb-[38px]`}>
        {t('closing.titleStart')}
        <br />
        {t('closing.titleEnd')}
      </h2>
      {action}
    </section>
  )
}
