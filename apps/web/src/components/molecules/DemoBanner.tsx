import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

/**
 * Says plainly that a screen shows example data, so nobody takes it for a real trip,
 * offer or price. Remove it from a page when that page reads the API.
 */
export function DemoBanner({ className }: { className?: string }) {
  const { t } = useTranslation('demo')
  return (
    <p role="note" className={cn('m-0 bg-sand px-5 py-2.5 text-sm text-ink md:px-[8vw]', className)}>
      <strong className="font-semibold">{t('title')}</strong> {t('text')}
    </p>
  )
}
