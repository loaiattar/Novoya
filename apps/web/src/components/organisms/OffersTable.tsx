import { Link } from '@tanstack/react-router'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { formatEuros } from '@/lib/format'

import type { PriceUnit } from './catalog'

export type OfferRow = {
  id: string
  title: string
  country: string
  city: string
  min_persons: number
  max_persons: number
  price_eur: number | null
  price_unit: PriceUnit | null
  featured: boolean
  active: boolean
  hidden: boolean
}

export type OfferSwitch = 'featured' | 'hidden'

type Props = {
  /** Names the table for screen readers: whose offers these are. */
  caption: string
  partnerId: string
  offers: OfferRow[]
  /** The offers whose switch is being saved: their switches wait. */
  savingIds?: ReadonlySet<string>
  onSwitch: (offerId: string, field: OfferSwitch, value: boolean) => void
}

/** A partner's offers, each opening its page, with its featured and hidden switches. */
export function OffersTable({ caption, partnerId, offers, savingIds = new Set(), onSwitch }: Props) {
  const id = useId()
  const { t, i18n } = useTranslation('admin')
  const toggle = (offer: OfferRow, field: OfferSwitch) => {
    const inputId = `${id}-${field}-${offer.id}`
    return (
      <label htmlFor={inputId} className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center">
        <input
          id={inputId}
          type="checkbox"
          checked={offer[field]}
          disabled={savingIds.has(offer.id)}
          onChange={(event) => onSwitch(offer.id, field, event.target.checked)}
          className="size-6 accent-ink disabled:opacity-60"
        />
        <span className="sr-only">
          {t(field === 'featured' ? 'offers.table.featuredOf' : 'offers.table.hiddenOf', { title: offer.title })}
        </span>
      </label>
    )
  }

  return (
    <table className="w-full border-collapse border-t border-line text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="text-start text-xs tracking-widest text-muted uppercase">
          <th scope="col" className="p-4 font-normal">
            {t('offers.table.offer')}
          </th>
          <th scope="col" className="hidden p-4 font-normal md:table-cell">
            {t('offers.table.price')}
          </th>
          <th scope="col" className="hidden p-4 font-normal md:table-cell">
            {t('offers.table.status')}
          </th>
          <th scope="col" className="p-4 font-normal">
            {t('offers.table.featured')}
          </th>
          <th scope="col" className="p-4 font-normal">
            {t('offers.table.hidden')}
          </th>
        </tr>
      </thead>
      <tbody>
        {offers.map((offer) => (
          <tr key={offer.id} className="border-t border-line">
            <th scope="row" className="p-4 text-start font-normal">
              <span className="grid">
                <Link
                  to="/admin/partners/$partnerId/offers/$offerId"
                  params={{ partnerId, offerId: offer.id }}
                  className="inline-flex min-h-11 items-center font-semibold underline underline-offset-4"
                >
                  {offer.title}
                </Link>
                <small className="mt-1 text-xs text-muted">
                  {t('place', { city: offer.city, country: offer.country })} ·{' '}
                  {t('offers.table.persons', { min: offer.min_persons, max: offer.max_persons })}
                </small>
              </span>
            </th>
            <td className="hidden p-4 md:table-cell">
              {offer.price_eur !== null && offer.price_unit !== null
                ? t('offers.table.priceOf', {
                    price: formatEuros(i18n.language, offer.price_eur),
                    unit: t(`units.${offer.price_unit}`),
                  })
                : t('offers.table.noPrice')}
            </td>
            <td className="hidden p-4 md:table-cell">{offer.active ? t('state.active') : t('state.inactive')}</td>
            <td className="px-2 py-1">{toggle(offer, 'featured')}</td>
            <td className="px-2 py-1">{toggle(offer, 'hidden')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
