import { useTranslation } from 'react-i18next'

import { formatDay } from '@/lib/format'

import { Chip } from '../atoms/Chip'

export type DaySummary = {
  number: number
  /** ISO date. */
  date: string
  title: string
  text: string
  mood: string
}

/** The demo plan's days on a vertical line. Day pages read real plans only (GET /plans/{id}). */
export function DayTimeline({ days }: { days: DaySummary[] }) {
  const { t, i18n } = useTranslation('plan')
  return (
    <section aria-label={t('daysLabel')} className="relative px-5 py-14 md:px-[14vw] md:py-22">
      <div aria-hidden="true" className="absolute top-14 bottom-24 left-[44px] w-px bg-line md:top-22 md:left-[calc(14vw+24px)]" />
      <ol>
        {days.map((day) => (
          <li key={day.number} className="relative grid grid-cols-[60px_1fr] md:grid-cols-[80px_1fr]">
            <div>
              <span
                aria-hidden="true"
                className="relative grid size-[49px] place-items-center rounded-full border border-ink bg-paper font-serif text-sm"
              >
                {String(day.number).padStart(2, '0')}
              </span>
            </div>
            <article className="grid gap-3.5 border-t border-line pt-5.5 pb-16 md:grid-cols-2 md:gap-10">
              <div>
                <p className="mb-3 text-xs tracking-[0.15em] text-muted uppercase">
                  {t('dayDate', { number: day.number, date: formatDay(i18n.language, day.date, false) })}
                </p>
                <h2 className="mb-4 text-[34px] leading-tight">{day.title}</h2>
                <Chip>{day.mood}</Chip>
              </div>
              <p className="m-0 text-sm leading-relaxed text-muted">{day.text}</p>
            </article>
          </li>
        ))}
      </ol>
    </section>
  )
}
