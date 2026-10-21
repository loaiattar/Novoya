import { useTranslation } from 'react-i18next'

import type { PlanItemResponse } from '../../api/generated/types.gen'

import { Chip } from '../atoms/Chip'

/** One offer of the plan. Never a price, never a partner (#31). */
export function PlanItem({ item }: { item: PlanItemResponse }) {
  const { t } = useTranslation('plan')
  return (
    <>
      {item.available ? (
        <>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            {item.kind && <Chip>{t(`live.kind.${item.kind}`)}</Chip>}
            {item.quantity > 1 && <Chip>{t('live.quantity', { count: item.quantity })}</Chip>}
          </div>
          <h3 className="mb-2 font-serif text-lg tracking-normal">{item.title}</h3>
          {item.description && <p className="m-0 text-sm leading-relaxed text-muted">{item.description}</p>}
        </>
      ) : (
        <p className="m-0 text-sm text-muted italic">{t('live.unavailable')}</p>
      )}
      {item.note && <p className="mt-2 text-sm leading-relaxed">{item.note}</p>}
    </>
  )
}
