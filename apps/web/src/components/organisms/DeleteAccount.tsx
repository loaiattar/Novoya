import { useState } from 'react'
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
 * button only opens the dialog; the dialog's action sends the request.
 */
export function DeleteAccount({ staff, onConfirm, pending, error }: Props) {
  const { t } = useTranslation('settings')
  const [asking, setAsking] = useState(false)

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
          <Button variant="outline" className="text-danger" onClick={() => setAsking(true)} disabled={pending}>
            {pending ? t('deleting') : t('deleteButton')}
          </Button>
          {error && (
            <p role="alert" className="mt-4 text-danger">
              {error}
            </p>
          )}
        </>
      )}
      <AlertDialog open={asking} onOpenChange={setAsking}>
        <AlertDialogContent className="rounded-none border-line bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif text-2xl font-normal tracking-normal">
              {t('confirmTitle')}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-muted">{t('confirmBody')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="min-h-11 rounded-full">{t('confirmCancel')}</AlertDialogCancel>
            <AlertDialogAction
              className="min-h-11 rounded-full bg-danger text-white hover:bg-danger/90"
              onClick={onConfirm}
            >
              {t('confirmAction')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
