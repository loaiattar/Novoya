import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { getClosestDatesOptions } from '@/api/generated/@tanstack/react-query.gen'
import { formatDayRange } from '@/lib/format'

import { Button } from '../atoms/Button'

type Props = {
  wishId: string
  persons: number
  startDate: string
  endDate: string
  /** Build the plan for other dates: the same length and group (#184). */
  onPickDates: (startDate: string, endDate: string) => void
  /** Send the answers to the agency as they are: an advisor builds the trip. */
  onSendAnyway: () => void
  sending: boolean
}

/**
 * What to do when no offer fits (#184): the nearest dates that work, before and after, and
 * sending the trip to the agency anyway. The dates come from the API, by the plan's own rule,
 * so choosing them never ends in "no offer fits".
 */
export function NoFitOptions({ wishId, persons, startDate, endDate, onPickDates, onSendAnyway, sending }: Props) {
  const { t, i18n } = useTranslation('preferences')
  const dates = useQuery({
    ...getClosestDatesOptions({
      path: { wish_id: wishId },
      query: { persons, start_date: startDate, end_date: endDate },
    }),
    retry: false,
  })
  const options = dates.data ?? []

  return (
    <section aria-labelledby="no-fit-options" className="mt-6 grid gap-4 border-s-2 border-coral ps-4">
      <h2 id="no-fit-options" className="m-0 text-lg font-semibold">
        {t('noFitOptions.title')}
      </h2>
      {options.length > 0 && (
        <div className="grid gap-2">
          <p className="m-0 text-sm text-muted">{t('noFitOptions.closest')}</p>
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
            {options.map((option) => (
              <li key={option.start_date}>
                <Button
                  type="button"
                  variant="outline"
                  disabled={sending}
                  onClick={() => onPickDates(option.start_date, option.end_date)}
                >
                  {t('noFitOptions.dates', {
                    dates: formatDayRange(i18n.language, option.start_date, option.end_date),
                    count: option.offers,
                  })}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {dates.isSuccess && options.length === 0 && (
        <p className="m-0 text-sm text-muted">{t('noFitOptions.noCloseDates')}</p>
      )}
      <div className="grid gap-2">
        <p className="m-0 text-sm text-muted">{t('noFitOptions.anywayText')}</p>
        <Button type="button" variant="coral" className="w-full md:w-fit" disabled={sending} onClick={onSendAnyway}>
          {sending ? t('noFitOptions.sending') : t('noFitOptions.anyway')}
        </Button>
      </div>
    </section>
  )
}
