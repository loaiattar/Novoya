import { useTranslation } from 'react-i18next'

import { formatDay, formatEuros } from '@/lib/format'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog'

type Props = {
  /** Decimal strings, as the API gives them. */
  total: string
  budget: string | null
  /** ISO day the quote stays valid until if it goes out now; null while nothing is asked. */
  validUntil: string | null
  onConfirm: () => void
  onCancel: () => void
}

/** Asks before the quote goes out: once sent, the client gets it and it cannot be changed. */
export function SendQuoteDialog({ total, budget, validUntil, onConfirm, onCancel }: Props) {
  const { t, i18n } = useTranslation('agent')
  const locale = i18n.language
  return (
    <AlertDialog open={validUntil !== null} onOpenChange={(next) => !next && onCancel()}>
      {validUntil !== null && (
        <AlertDialogContent className="rounded-none border-line bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif text-2xl font-normal tracking-normal">
              {t('quote.confirmTitle')}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-muted">{t('quote.confirmBody')}</AlertDialogDescription>
          </AlertDialogHeader>
          <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
            <dt className="text-muted">{t('quote.total')}</dt>
            <dd className="m-0 font-serif text-lg">{formatEuros(locale, Number(total))}</dd>
            <dt className="text-muted">{t('quote.budget')}</dt>
            <dd className="m-0">{budget === null ? t('request.noBudget') : formatEuros(locale, Number(budget))}</dd>
          </dl>
          <p className="m-0 text-sm">{t('quote.validUntil', { date: formatDay(locale, validUntil) })}</p>
          <AlertDialogFooter>
            <AlertDialogCancel className="min-h-11 rounded-full">{t('quote.cancel')}</AlertDialogCancel>
            <AlertDialogAction className="min-h-11 rounded-full" onClick={onConfirm}>
              {t('quote.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      )}
    </AlertDialog>
  )
}
