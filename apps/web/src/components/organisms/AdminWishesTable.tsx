import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { datesOf, placeOf, type WishStatus } from '@/domain/admin/activity'
import { formatShortDate } from '@/lib/format'

import { StatusPill } from '../atoms/StatusPill'
import { PersonCell } from '../molecules/PersonCell'

export type AdminWishRow = {
  id: string
  status: WishStatus
  text: string
  country: string | null
  city: string | null
  start_date: string | null
  end_date: string | null
  updated_at: string
  client: { name: string | null; email: string } | null
}

type Props = { wishes: AdminWishRow[] }

/** Every client's wishes with their status. A planned wish leads to its plans. */
export function AdminWishesTable({ wishes }: Props) {
  const { t, i18n } = useTranslation('admin')
  return (
    <table className="w-full border-collapse border-t border-line text-sm">
      <caption className="sr-only">{t('activity.wishes.caption')}</caption>
      <thead>
        <tr className="text-xs tracking-widest text-muted uppercase">
          <th scope="col" className="px-2 py-4 text-start font-normal md:p-4">
            {t('activity.wishes.wish')}
          </th>
          <th scope="col" className="px-2 py-4 text-start font-normal md:p-4">
            {t('activity.wishes.client')}
          </th>
          <th scope="col" className="hidden p-4 text-start font-normal md:table-cell">
            {t('activity.wishes.dates')}
          </th>
          <th scope="col" className="px-2 py-4 text-start font-normal md:p-4">
            {t('activity.wishes.status')}
          </th>
          <th scope="col" className="hidden p-4 text-start font-normal md:table-cell">
            {t('activity.wishes.updated')}
          </th>
        </tr>
      </thead>
      <tbody>
        {wishes.map((wish) => (
          <tr key={wish.id} className="border-t border-line align-top">
            <th scope="row" className="px-2 py-4 text-start font-normal md:p-4">
              <span className="grid max-w-[38ch]">
                <span className="line-clamp-2">{wish.text}</span>
                <small className="mt-1 text-xs text-muted">{placeOf(wish) ?? t('activity.noPlace')}</small>
              </span>
            </th>
            <td className="px-2 py-4 md:p-4">
              <PersonCell person={wish.client} fallback={t('activity.noClient')} />
            </td>
            <td className="hidden p-4 md:table-cell">
              {datesOf(i18n.language, wish) ?? <span className="text-muted">{t('activity.noDates')}</span>}
            </td>
            <td className="px-2 py-4 md:p-4">
              <span className="grid justify-items-start gap-1">
                <StatusPill>{t(`activity.wishStatus.${wish.status}`)}</StatusPill>
                {wish.status === 'planned' && (
                  <Link
                    to="/admin/activity"
                    search={{ tab: 'plans', wish: wish.id }}
                    className="inline-flex min-h-11 items-center text-xs underline underline-offset-4"
                  >
                    {t('activity.wishes.seePlans')}
                  </Link>
                )}
              </span>
            </td>
            <td className="hidden p-4 md:table-cell">{formatShortDate(i18n.language, wish.updated_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
