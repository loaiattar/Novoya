import { useTranslation } from 'react-i18next'

import { formatDateTime, formatDayRange } from '@/lib/format'

import { Chip } from '../atoms/Chip'
import { Eyebrow } from '../atoms/Eyebrow'

type Props = {
  version: number
  /** ISO date and time. */
  updatedAt: string
  place: string
  tagline: string
  startDate: string
  endDate: string
  travellers: number
  tags: string[]
}

/** The top of a plan: its version, title and summary. Never a price (#31). */
export function PlanHeader({ version, updatedAt, place, tagline, startDate, endDate, travellers, tags }: Props) {
  const { t, i18n } = useTranslation('plan')
  return (
    <section className="bg-ivory px-5 pt-16 pb-10 md:flex md:items-end md:justify-between md:px-[8vw] md:pt-25 md:pb-20">
      <div>
        <div className="flex flex-wrap items-center gap-x-4">
          <Eyebrow>{t('eyebrow', { version })}</Eyebrow>
          <span className="mb-6 text-xs text-muted">{t('updated', { date: formatDateTime(i18n.language, updatedAt) })}</span>
        </div>
        <h1 className="m-0 text-display-m">
          {t('placeHeading', { place })}{' '}
          <br />
          <em>{tagline}</em>
        </h1>
      </div>
      <div className="mt-9 md:mt-0 md:text-right">
        <p className="m-1.5 font-serif text-lg">{formatDayRange(i18n.language, startDate, endDate)}</p>
        <p className="m-1.5 font-serif text-lg">{t('travellers', { count: travellers })}</p>
        <ul aria-label={t('wishesLabel')} className="mt-5 flex flex-wrap gap-1.5 md:justify-end">
          {tags.map((tag) => (
            <li key={tag}>
              <Chip>{tag}</Chip>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
