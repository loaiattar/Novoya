import { useId, useState } from 'react'
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
import type { Role } from './roles'

export type RoleChange = { userId: string; name: string; from: Role; to: Role }

type Props = {
  /** The change waiting for confirmation, or null when there is none. */
  change: RoleChange | null
  /** The roles to pick from in the dialog, `change.to` selected first. Without it, the role is set. */
  choices?: Role[]
  onConfirm: (change: RoleChange) => void
  onCancel: () => void
}

/**
 * Asks before a role changes. A role gives access to the agency or the administration, and a
 * closed <select> can change value from the keyboard alone, so nothing is sent without this step.
 */
export function RoleChangeDialog({ change, choices, onConfirm, onCancel }: Props) {
  return (
    <AlertDialog open={change !== null} onOpenChange={(open) => !open && onCancel()}>
      {/* Keyed by the change: the picked role starts again from `change.to` each time. */}
      {change && <Content key={`${change.userId}-${change.to}`} change={change} choices={choices} onConfirm={onConfirm} />}
    </AlertDialog>
  )
}

function Content({ change, choices, onConfirm }: { change: RoleChange; choices?: Role[]; onConfirm: Props['onConfirm'] }) {
  const { t } = useTranslation('admin')
  const id = useId()
  const [to, setTo] = useState<Role>(change.to)
  return (
    <AlertDialogContent className="rounded-none border-line bg-white">
      <AlertDialogHeader>
        <AlertDialogTitle className="font-serif text-2xl font-normal tracking-normal">
          {t('confirm.title', { name: change.name })}
        </AlertDialogTitle>
        <AlertDialogDescription className="text-muted">
          {t('confirm.body', { name: change.name, from: t(`roles.${change.from}`), to: t(`roles.${to}`) })}
        </AlertDialogDescription>
      </AlertDialogHeader>
      {choices && (
        <div className="grid gap-1.5">
          <label htmlFor={id} className="text-sm">
            {t('confirm.newRole')}
          </label>
          <select
            id={id}
            value={to}
            onChange={(event) => setTo(event.target.value as Role)}
            className="min-h-11 border border-line bg-white px-2.5"
          >
            {choices.map((role) => (
              <option key={role} value={role}>
                {t(`roles.${role}`)}
              </option>
            ))}
          </select>
        </div>
      )}
      <AlertDialogFooter>
        <AlertDialogCancel className="min-h-11 rounded-full">{t('confirm.cancel')}</AlertDialogCancel>
        <AlertDialogAction className="min-h-11 rounded-full" onClick={() => onConfirm({ ...change, to })}>
          {t('confirm.action')}
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  )
}
