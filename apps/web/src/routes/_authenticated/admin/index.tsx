import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useDeferredValue, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  changeUserRoleMutation,
  listUsersOptions,
  listUsersQueryKey,
} from '../../../api/generated/@tanstack/react-query.gen'
import { Eyebrow } from '../../../components/atoms/Eyebrow'
import { Input } from '../../../components/atoms/Input'
import { ErrorNote } from '../../../components/molecules/ErrorNote'
import { RoleChangeDialog, type RoleChange } from '../../../components/organisms/RoleChangeDialog'
import { type Role, ROLES } from '../../../components/organisms/roles'
import { UsersTable } from '../../../components/organisms/UsersTable'

// The guard is in route.tsx: admins only.
export const Route = createFileRoute('/_authenticated/admin/')({
  component: AdminPage,
})

function AdminPage() {
  const { me } = Route.useRouteContext()
  const { t } = useTranslation('admin')
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [role, setRole] = useState<Role | ''>('')
  // A role change waits here until the admin confirms it.
  const [pendingChange, setPendingChange] = useState<RoleChange | null>(null)
  const q = useDeferredValue(search.trim())

  const query = { q: q || undefined, role: role || undefined, limit: 50 }
  const users = useQuery({ ...listUsersOptions({ query }), placeholderData: keepPreviousData })
  const changeRole = useMutation({
    ...changeUserRoleMutation(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: listUsersQueryKey() }),
  })

  return (
    <>
      <Eyebrow>{t('eyebrow')}</Eyebrow>
      <h1 className="m-0 text-[39px] md:text-[50px]">{t('title')}</h1>

      <div className="mt-10 mb-4 flex flex-col gap-2.5 md:flex-row">
        <label className="sr-only" htmlFor="admin-search">
          {t('searchLabel')}
        </label>
        <Input
          id="admin-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t('searchPlaceholder')}
          className="md:max-w-[350px]"
        />
        <label className="sr-only" htmlFor="admin-role">
          {t('roleFilter')}
        </label>
        <select
          id="admin-role"
          value={role}
          onChange={(event) => setRole(event.target.value as Role | '')}
          className="min-h-11 border border-line bg-white px-3"
        >
          <option value="">{t('allRoles')}</option>
          {ROLES.map((value) => (
            <option key={value} value={value}>
              {t(`roles.${value}`)}
            </option>
          ))}
        </select>
      </div>

      {changeRole.isError && (
        <p role="alert" className="mb-4 text-danger">
          {t('changeFailed')}
        </p>
      )}

      {users.isPending ? (
        <p className="py-6 text-muted">{t('loading')}</p>
      ) : users.isError ? (
        <ErrorNote message={t('loadFailed')} onRetry={() => users.refetch()} />
      ) : users.data.length === 0 ? (
        <p className="py-6 text-muted">{t('empty')}</p>
      ) : (
        <UsersTable
          users={users.data}
          meId={me.id}
          savingId={changeRole.isPending ? changeRole.variables?.path.user_id : undefined}
          onChangeRole={(userId, next) => {
            const user = users.data.find((row) => row.id === userId)
            if (!user || user.role === next) return
            setPendingChange({ userId, name: user.name ?? user.email, from: user.role, to: next })
          }}
        />
      )}
      <p className="mt-5 text-xs text-muted">
        {t('note')}
      </p>
      <RoleChangeDialog
        change={pendingChange}
        onCancel={() => setPendingChange(null)}
        onConfirm={(change) => {
          setPendingChange(null)
          changeRole.mutate({ path: { user_id: change.userId }, body: { role: change.to } })
        }}
      />
    </>
  )
}
