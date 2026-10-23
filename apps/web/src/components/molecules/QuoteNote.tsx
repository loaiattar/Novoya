import { useTranslation } from 'react-i18next'

/** Tells the client that a plan never shows a price: the price comes in a quote. */
export function QuoteNote() {
  const { t } = useTranslation('plan')
  return (
    <p className="m-0 px-5 py-8 text-sm text-muted md:px-[8vw]">
      {t('priceNote')}
    </p>
  )
}
