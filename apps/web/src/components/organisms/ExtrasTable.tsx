import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { formatEuros } from '@/lib/format'

export type ExtraPricing = 'included' | 'supplement' | 'on_quote'

export type ExtraRow = {
  id: string
  /** From DÉTOUR, as it names it. */
  category: string
  label: string
  pricing: ExtraPricing
  /** Only for a supplement. */
  supplement_eur: number | null
  /** From DÉTOUR, as it names it: per person, per room… */
  unit: string
  active: boolean
  hidden: boolean
}

type Props = {
  extras: ExtraRow[]
  /** The extras whose switch is being saved: their switches wait. */
  savingIds?: ReadonlySet<string>
  onHide: (extraId: string, hidden: boolean) => void
}

/** Every extra from DÉTOUR, read-only, with the switch that hides it from clients. */
export function ExtrasTable({ extras, savingIds = new Set(), onHide }: Props) {
  const id = useId()
  const { t, i18n } = useTranslation('admin')
  const pricingOf = (extra: ExtraRow) =>
    extra.pricing === 'supplement' && extra.supplement_eur !== null
      ? t('extras.table.supplementOf', { price: formatEuros(i18n.language, extra.supplement_eur), unit: extra.unit })
      : t(`extras.pricing.${extra.pricing}`)

  return (
    <table className="w-full border-collapse border-t border-line text-sm">
      <caption className="sr-only">{t('extras.table.caption')}</caption>
      <thead>
        <tr className="text-xs tracking-widest text-muted uppercase">
          <th scope="col" className="p-4 text-start font-normal">
            {t('extras.table.extra')}
          </th>
          <th scope="col" className="hidden p-4 text-start font-normal md:table-cell">
            {t('extras.table.pricing')}
          </th>
          <th scope="col" className="hidden p-4 text-start font-normal md:table-cell">
            {t('extras.table.status')}
          </th>
          <th scope="col" className="px-2 py-4 text-center font-normal">
            {t('extras.table.hidden')}
          </th>
        </tr>
      </thead>
      <tbody>
        {extras.map((extra) => {
          const inputId = `${id}-hidden-${extra.id}`
          return (
            <tr key={extra.id} className="border-t border-line">
              <th scope="row" className="p-4 text-start font-normal">
                <span className="grid">
                  <b className="font-semibold">{extra.label}</b>
                  <small className="mt-1 text-xs text-muted">
                    {extra.category}
                    {/* On a phone the pricing and the status columns are hidden: they come here. */}
                    <span className="md:hidden">
                      {' '}
                      · {pricingOf(extra)} · {extra.active ? t('state.active') : t('state.inactive')}
                    </span>
                  </small>
                </span>
              </th>
              <td className="hidden p-4 md:table-cell">{pricingOf(extra)}</td>
              <td className="hidden p-4 md:table-cell">{extra.active ? t('state.active') : t('state.inactive')}</td>
              <td className="px-2 py-1 text-center">
                <label htmlFor={inputId} className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center">
                  <input
                    id={inputId}
                    type="checkbox"
                    checked={extra.hidden}
                    disabled={savingIds.has(extra.id)}
                    onChange={(event) => onHide(extra.id, event.target.checked)}
                    className="size-6 accent-ink disabled:opacity-60"
                  />
                  <span className="sr-only">{t('extras.table.hiddenOf', { label: extra.label })}</span>
                </label>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
