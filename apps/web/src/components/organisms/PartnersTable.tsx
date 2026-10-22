import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { StatusPill } from '../atoms/StatusPill'
import type { CatalogKind } from './catalog'

export type PartnerRow = {
  id: string
  name: string
  kind: CatalogKind
  country: string
  city: string
  active: boolean
  hidden: boolean
  imported: boolean
}

type Props = { partners: PartnerRow[] }

/** Every partner with where it is, its state and where it comes from. Each opens its page. */
export function PartnersTable({ partners }: Props) {
  const { t } = useTranslation('admin')
  return (
    <table className="w-full border-collapse border-t border-line text-sm">
      <caption className="sr-only">{t('partners.table.caption')}</caption>
      <thead>
        <tr className="text-start text-xs tracking-widest text-muted uppercase">
          <th scope="col" className="p-4 font-normal">
            {t('partners.table.partner')}
          </th>
          <th scope="col" className="hidden p-4 font-normal md:table-cell">
            {t('partners.table.kind')}
          </th>
          <th scope="col" className="p-4 font-normal">
            {t('partners.table.status')}
          </th>
          <th scope="col" className="p-4 font-normal">
            {t('partners.table.source')}
          </th>
        </tr>
      </thead>
      <tbody>
        {partners.map((partner) => (
          <tr key={partner.id} className="border-t border-line">
            <th scope="row" className="p-4 text-start font-normal">
              <span className="grid">
                <Link
                  to="/admin/partners/$partnerId"
                  params={{ partnerId: partner.id }}
                  className="inline-flex min-h-11 items-center font-semibold underline underline-offset-4"
                >
                  {partner.name}
                </Link>
                <small className="mt-1 text-xs text-muted">
                  {t('place', { city: partner.city, country: partner.country })}
                </small>
              </span>
            </th>
            <td className="hidden p-4 md:table-cell">{t(`kinds.${partner.kind}`)}</td>
            <td className="p-4">
              <span className="flex flex-wrap gap-1.5">
                <span>{partner.active ? t('state.active') : t('state.inactive')}</span>
                {partner.hidden && <StatusPill highlight>{t('state.hidden')}</StatusPill>}
              </span>
            </td>
            <td className="p-4">
              {partner.imported ? <StatusPill>{t('source.importedShort')}</StatusPill> : t('source.manualShort')}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
