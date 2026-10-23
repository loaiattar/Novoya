import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Trip } from '@/api/generated/types.gen'
import { tripStatus, tripTarget } from '@/domain/trips/trip'
import { formatDateTime, formatDayRange } from '@/lib/format'

import { StatusPill } from '../atoms/StatusPill'

/** The link of a trip: to its quote, its plan, its preference panel or the wish page. */
function TripLink({ trip, className, children }: { trip: Trip; className: string; children: ReactNode }) {
  const target = tripTarget(trip)
  switch (target.kind) {
    case 'quote':
      return (
        <Link to="/quotes/$quoteId" params={{ quoteId: target.quoteId }} className={className}>
          {children}
        </Link>
      )
    case 'plan':
      return (
        <Link to="/plans/$planId" params={{ planId: target.planId }} className={className}>
          {children}
        </Link>
      )
    case 'panel':
      return (
        <Link to="/wish/$wishId/preferences" params={{ wishId: target.wishId }} className={className}>
          {children}
        </Link>
      )
    case 'wish':
      return (
        <Link to="/wish" className={className}>
          {children}
        </Link>
      )
  }
}

/** The client's trips, newest first, one card each. A card opens the page the trip is at. */
export function TripList({ trips }: { trips: Trip[] }) {
  const { t, i18n } = useTranslation('trips')
  const locale = i18n.language
  return (
    <ul aria-label={t('listLabel')} className="flex max-w-3xl flex-col gap-3">
      {trips.map((trip) => {
        const status = tripStatus(trip)
        const place = [trip.city, trip.country].filter(Boolean).join(', ') || t('noDestination')
        const dates =
          trip.start_date && trip.end_date ? formatDayRange(locale, trip.start_date, trip.end_date) : t('datesToBeSet')
        return (
          <li key={trip.wish_id}>
            <TripLink trip={trip} className="grid gap-2 border border-line bg-white p-4 hover:border-ink sm:p-5">
              <span className="flex flex-wrap items-center justify-between gap-2">
                <StatusPill highlight={status === 'quoted'}>{t(`status.${status}`)}</StatusPill>
                <time dateTime={trip.created_at} className="text-xs text-muted">
                  {t('sentOn', { date: formatDateTime(locale, trip.created_at) })}
                </time>
              </span>
              <small className="text-xs text-muted">{t('placeAndDates', { place, dates })}</small>
              <b className="line-clamp-2 font-serif text-[17px] font-normal">{trip.text}</b>
              {status === 'sent' && (
                <span className="text-xs text-muted">{t('answerWithin', { count: trip.answer_within_days })}</span>
              )}
              {trip.persons !== null && (
                <span className="text-xs text-muted">{t('travellers', { count: trip.persons })}</span>
              )}
            </TripLink>
          </li>
        )
      })}
    </ul>
  )
}
