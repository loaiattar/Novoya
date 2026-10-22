import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { formatDay } from '@/lib/format'

export type ReviewRow = {
  id: string
  country: string
  city: string
  rating: number
  reviewed_on: string
  text: string
  author: string
  hidden: boolean
}

type Props = {
  reviews: ReviewRow[]
  savingIds?: ReadonlySet<string>
  onHide: (reviewId: string, hidden: boolean) => void
}

/** Published reviews, including hidden ones, each with the admin's hide switch. */
export function ReviewsTable({ reviews, savingIds = new Set(), onHide }: Props) {
  const id = useId()
  const { t, i18n } = useTranslation('admin')

  return (
    <table className="w-full border-collapse border-t border-line text-sm">
      <caption className="sr-only">{t('reviews.table.caption')}</caption>
      <thead>
        <tr className="text-xs tracking-widest text-muted uppercase">
          <th scope="col" className="p-4 text-start font-normal">
            {t('reviews.table.review')}
          </th>
          <th scope="col" className="hidden p-4 text-start font-normal md:table-cell">
            {t('reviews.table.rating')}
          </th>
          <th scope="col" className="hidden p-4 text-start font-normal md:table-cell">
            {t('reviews.table.date')}
          </th>
          <th scope="col" className="hidden p-4 text-start font-normal lg:table-cell">
            {t('reviews.table.text')}
          </th>
          <th scope="col" className="px-2 py-4 text-center font-normal">
            {t('reviews.table.hidden')}
          </th>
        </tr>
      </thead>
      <tbody>
        {reviews.map((review) => {
          const inputId = `${id}-hidden-${review.id}`
          return (
            <tr key={review.id} className="border-t border-line">
              <th scope="row" className="p-4 text-start font-normal">
                <span className="grid">
                  <span className="font-semibold">{review.author}</span>
                  <small className="mt-1 text-xs text-muted">
                    {t('place', { city: review.city, country: review.country })}
                  </small>
                  <small className="mt-1 text-xs text-muted md:hidden">
                    {t('reviews.table.ratingOf', { rating: review.rating })} ·{' '}
                    {formatDay(i18n.language, review.reviewed_on)}
                  </small>
                  <small className="mt-2 text-xs font-normal lg:hidden">{review.text}</small>
                </span>
              </th>
              <td className="hidden p-4 md:table-cell">{t('reviews.table.ratingOf', { rating: review.rating })}</td>
              <td className="hidden p-4 md:table-cell">
                <time dateTime={review.reviewed_on}>{formatDay(i18n.language, review.reviewed_on)}</time>
              </td>
              <td className="hidden p-4 align-top lg:table-cell">{review.text}</td>
              <td className="px-2 py-1 text-center">
                <label htmlFor={inputId} className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center">
                  <input
                    id={inputId}
                    type="checkbox"
                    checked={review.hidden}
                    disabled={savingIds.has(review.id)}
                    onChange={(event) => onHide(review.id, event.target.checked)}
                    className="size-6 accent-ink disabled:opacity-60"
                  />
                  <span className="sr-only">{t('reviews.table.hiddenOf', { author: review.author })}</span>
                </label>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
