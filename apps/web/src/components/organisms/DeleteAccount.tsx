import { useTranslation } from 'react-i18next'

import { Button } from '../atoms/Button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../ui/alert-dialog'

type Props = {
  /** Agency staff cannot delete their account here (the API answers 403 staff_account). */
  staff: boolean
  onConfirm: () => void
  pending: boolean
  /** Why the last attempt failed, already translated. */
  error?: string
}

/**
 * Deletes the account after one confirmation step. Nothing can bring the data back, so the
 * button only opens the dialog; the dialog's action sends the request. The button is the
 * dialog's trigger, so closing the dialog puts the focus back on it.
 */
export function DeleteAccount({ staff, onConfirm, pending, error }: Props) {
  const { t } = useTranslation('settings')

  return (
    <section aria-labelledby="delete-title" className="mt-12 max-w-[560px]">
      <h2 id="delete-title" className="mb-2 text-[30px] leading-tight">
        {t('deleteTitle')}
      </h2>
      {staff ? (
        <p className="text-muted">{t('staffAccount')}</p>
      ) : (
        <>
          <p className="mb-4 text-muted">{t('deleteBody')}</p>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" className="text-danger" disabled={pending}>
                {pending ? t('deleting') : t('deleteButton')}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent className="rounded-none border-line bg-white">
              <AlertDialogHeader>
                <AlertDialogTitle className="font-serif text-2xl font-normal tracking-normal">
                  {t('confirmTitle')}
                </AlertDialogTitle>
                <AlertDialogDescription className="text-muted">{t('confirmBody')}</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel className="min-h-11 rounded-full">{t('confirmCancel')}</AlertDialogCancel>
                <AlertDialogAction variant="destructive" className="min-h-11 rounded-full" onClick={onConfirm}>
                  {t('confirmAction')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          {error && (
            <p role="alert" className="mt-4 text-danger">
              {error}
            </p>
          )}
        </>
      )}
    </section>
  )
}
