import { useTranslation } from 'react-i18next'

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
import type { UserStatus } from './UsersTable'

export type StatusChange = { userId: string; name: string; to: UserStatus }

type Props = {
  /** The change waiting for confirmation, or null when there is none. */
  change: StatusChange | null
  onConfirm: (change: StatusChange) => void
  onCancel: () => void
}

/** Asks before an account is disabled or enabled: disabling signs the person out at once. */
export function StatusChangeDialog({ change, onConfirm, onCancel }: Props) {
  const { t } = useTranslation('admin')
  const action = change?.to === 'disabled' ? 'disable' : 'enable'
  return (
    <AlertDialog open={change !== null} onOpenChange={(open) => !open && onCancel()}>
      {change && (
        <AlertDialogContent className="rounded-none border-line bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif text-2xl font-normal tracking-normal">
              {t(`statusConfirm.${action}.title`, { name: change.name })}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-muted">
              {t(`statusConfirm.${action}.body`, { name: change.name })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="min-h-11 rounded-full">{t('confirm.cancel')}</AlertDialogCancel>
            <AlertDialogAction className="min-h-11 rounded-full" onClick={() => onConfirm(change)}>
              {t(`statusConfirm.${action}.action`)}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      )}
    </AlertDialog>
  )
}
