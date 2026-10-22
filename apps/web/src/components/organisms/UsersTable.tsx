import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { formatShortDate } from '@/lib/format'

import { Button } from '../atoms/Button'

import { GIVEN_ROLES, isAdminRole, type Role } from './roles'

export type UserRow = {
  id: string
  name: string | null
  email: string
  role: Role
  status: UserStatus
  /** When the account was last disabled or enabled, or null if it never was. */
  status_changed_at: string | null
  email_verified: boolean
  created_at: string
}

export type UserStatus = 'active' | 'disabled'

type Props = {
  users: UserRow[]
  /** The signed-in admin: they cannot change their own role. */
  meId: string
  /** Their role: only a super admin acts on admins. Nobody acts on a super admin here. */
  meRole: Role
  /** The users whose role or status is being saved. */
  savingIds?: ReadonlySet<string>
  onChangeRole: (userId: string, role: Role) => void
  onChangeStatus: (userId: string, status: UserStatus) => void
}

/** The users with their role and account status, which an admin can change. */
export function UsersTable({
  users,
  meId,
  meRole,
  savingIds = new Set(),
  onChangeRole,
  onChangeStatus,
}: Props) {
  const id = useId()
  const { t, i18n } = useTranslation('admin')
  const superAdmin = meRole === 'super_admin'
  return (
    <table className="w-full border-collapse border-t border-line text-sm">
      <caption className="sr-only">{t('table.caption')}</caption>
      <thead>
        <tr className="text-left text-xs tracking-widest text-muted uppercase">
          <th scope="col" className="px-2 py-4 font-normal md:p-4">
            {t('table.user')}
          </th>
          <th scope="col" className="px-2 py-4 font-normal md:p-4">
            {t('table.role')}
          </th>
          <th scope="col" className="px-2 py-4 font-normal md:p-4">
            {t('table.account')}
          </th>
          <th scope="col" className="hidden p-4 font-normal md:table-cell">
            {t('table.email')}
          </th>
          <th scope="col" className="hidden p-4 font-normal md:table-cell">
            {t('table.joined')}
          </th>
        </tr>
      </thead>
      <tbody>
        {users.map((user) => {
          const isMe = user.id === meId
          // Nobody changes their own role or account, only a super admin acts on admins, and a
          // super admin's role and account are managed on the server only. Agent and admin
          // need a verified email (the API enforces all of it too).
          const adminOutOfReach = user.role === 'super_admin' || (!superAdmin && isAdminRole(user.role))
          const locked = isMe || adminOutOfReach || !user.email_verified
          const statusLocked = isMe || adminOutOfReach
          const disabled = user.status === 'disabled'
          const saving = savingIds.has(user.id)
          const name = user.name ?? user.email
          return (
            <tr key={user.id} className="border-t border-line">
              <th scope="row" className="px-2 py-4 text-left font-normal md:p-4">
                <span className="grid">
                  <b className="font-semibold">{user.name ?? user.email}</b>
                  <small className="mt-1 text-xs break-all text-muted">{user.email}</small>
                </span>
              </th>
              <td className="px-2 py-4 md:p-4">
                <label htmlFor={`${id}-${user.id}`} className="sr-only">
                  {t('table.roleOf', { name })}
                </label>
                <select
                  id={`${id}-${user.id}`}
                  value={user.role}
                  disabled={locked || saving}
                  onChange={(event) => onChangeRole(user.id, event.target.value as Role)}
                  className="min-h-11 border border-line bg-white px-2.5 disabled:text-muted"
                >
                  {/* The super admin role is never offered: only the server command gives it. It is
                      listed only to show the current role of a super admin. */}
                  {(user.role === 'super_admin' ? [...GIVEN_ROLES, user.role] : GIVEN_ROLES).map((role) => (
                    // A disabled account stays a client until it is enabled again, and only a
                    // super admin gives the admin role.
                    <option
                      key={role}
                      value={role}
                      disabled={role === 'super_admin' || (disabled && role !== 'client') || (!superAdmin && isAdminRole(role))}
                    >
                      {t(`roles.${role}`)}
                    </option>
                  ))}
                </select>
              </td>
              <td className="px-2 py-4 md:p-4">
                <span className="grid justify-items-start">
                  <span className="whitespace-nowrap">
                    <span
                      aria-hidden="true"
                      className={`mr-1.5 inline-block size-1.5 rounded-full ${disabled ? 'bg-danger' : 'bg-ok'}`}
                    />
                    {t(`status.${user.status}`)}
                  </span>
                  {disabled && user.status_changed_at && (
                    <small className="mt-1 text-xs text-muted">
                      {t('table.disabledOn', { date: formatShortDate(i18n.language, user.status_changed_at) })}
                    </small>
                  )}
                  {!statusLocked && (
                    <Button
                      variant="link"
                      size="inline"
                      disabled={saving}
                      aria-label={t(disabled ? 'table.enableOf' : 'table.disableOf', { name })}
                      onClick={() => onChangeStatus(user.id, disabled ? 'active' : 'disabled')}
                      className="min-h-11 text-xs"
                    >
                      {t(disabled ? 'statusAction.enable' : 'statusAction.disable')}
                    </Button>
                  )}
                </span>
              </td>
              <td className="hidden p-4 md:table-cell">
                <span
                  aria-hidden="true"
                  className={`mr-1.5 inline-block size-1.5 rounded-full ${user.email_verified ? 'bg-ok' : 'bg-pending'}`}
                />
                {isMe ? t('table.you') : user.email_verified ? t('table.verified') : t('table.pending')}
              </td>
              <td className="hidden p-4 md:table-cell">{formatShortDate(i18n.language, user.created_at)}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
