import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { Seal } from '../atoms/Seal'

type Props = {
  title: string
  /** The current preview's version, or null for a draft. */
  version: number | null
  planId?: string
}

/** One trip's details, with a link to its current plan when there is one. */
export function HistoryPanel({ title, version, planId }: Props) {
  const { t } = useTranslation('trips')
  const summary = version === null ? t('draftSummary') : t('previewSummary', { version })
  return (
    <section aria-label={t('history.label', { title })} className="mt-6 flex min-h-0 flex-col border border-line bg-white lg:mt-0">
      <div className="flex items-center gap-3 border-b border-line p-4.5">
        <Seal tone="ink" />
        <div className="flex-1">
          <small className="text-xs tracking-[0.14em] text-muted uppercase">{t('history.eyebrow')}</small>
          <h2 className="my-1 text-xl tracking-normal">{title}</h2>
          <p className="m-0 text-xs text-muted">{summary}</p>
        </div>
      </div>
      {planId && version !== null && (
        <div className="m-4.5 grid grid-cols-[1fr_auto] items-center bg-ivory p-3">
          <span className="font-serif">{t('previewVersion', { version })}</span>
          <Link
            to="/plans/$planId"
            params={{ planId }}
            className="col-start-2 row-span-2 flex min-h-11 items-center text-xs text-ink underline underline-offset-4"
          >
            {t('history.viewPreview')}
          </Link>
          <small className="text-xs text-muted">{t('history.current')}</small>
        </div>
      )}
    </section>
  )
}
