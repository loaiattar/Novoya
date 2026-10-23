import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, redirect } from '@tanstack/react-router'
import { useDeferredValue, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { changeUserRoleMutation, listUsersOptions, listUsersQueryKey } from '../../../../api/generated/@tanstack/react-query.gen'
import type { UserResponse } from '../../../../api/generated/types.gen'
import { Button } from '../../../../components/atoms/Button'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { Input } from '../../../../components/atoms/Input'
import { ErrorNote } from '../../../../components/molecules/ErrorNote'
import { RoleChangeDialog, type RoleChange } from '../../../../components/organisms/RoleChangeDialog'
import { adminOutOfReach, canGiveRole, type Role } from '../../../../components/organisms/roles'
import { canOpen } from '../../../../domain/auth/roles'
import { roleErrorKey } from '../../../-roleErrors'

// The roles an admin can go back to. The super admin role is never offered: the server gives it.
const REVOKE_TO: Role[] = ['agent', 'client']

const COMMANDS = [
  { label: 'admins.help.grant', command: 'python -m novoya_api.accounts.presentation.cli grant-role --email <email> --role super_admin' },
  { label: 'admins.help.demote', command: 'python -m novoya_api.accounts.presentation.cli grant-role --email <email> --role admin' },
] as const

// The admin area (../route.tsx) lets admins in; this page is for a super admin only.
export const Route = createFileRoute('/_authenticated/admin/admins/')({
  beforeLoad: ({ context }) => {
    if (!canOpen(context.me.role, 'admins')) throw redirect({ to: '/admin' })
  },
  component: AdminsPage,
})

/** The admin team: who has the admin role, and the super admin gives or takes it. */
function AdminsPage() {
  const { me } = Route.useRouteContext()
  const { t } = useTranslation('admin')
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [pending, setPending] = useState<{ change: RoleChange; choices?: Role[] } | null>(null)
  const q = useDeferredValue(search.trim())

  // GET /admin/users filters on one role: one request for each admin role.
  const admins = useQuery(listUsersOptions({ query: { role: 'admin', limit: 100 } }))
  const superAdmins = useQuery(listUsersOptions({ query: { role: 'super_admin', limit: 100 } }))
  // The search asks for clients and agents, so that admins never take the matches' places.
  const foundClients = useQuery({ ...listUsersOptions({ query: { q, role: 'client', limit: 10 } }), enabled: q.length >= 2 })
  const foundAgents = useQuery({ ...listUsersOptions({ query: { q, role: 'agent', limit: 10 } }), enabled: q.length >= 2 })
  // Refetch after a failure too: the row may have changed in another tab.
  const changeRole = useMutation({
    ...changeUserRoleMutation(),
    onSettled: () => queryClient.invalidateQueries({ queryKey: listUsersQueryKey() }),
  })
  const saving = changeRole.isPending ? changeRole.variables?.path.user_id : undefined

  const team = [...(superAdmins.data ?? []), ...(admins.data ?? [])]
  const candidates = [...(foundAgents.data ?? []), ...(foundClients.data ?? [])]
  const name = (user: UserResponse) => user.name ?? user.email

  return (
    <>
      <Eyebrow>{t('eyebrow')}</Eyebrow>
      <h1 className="m-0 text-[39px] md:text-[50px]">{t('admins.title')}</h1>
      <p className="mt-3 mb-8 max-w-[60ch] text-muted">{t('admins.intro')}</p>

      {changeRole.isError && (
        <p role="alert" className="mb-4 text-danger">
          {t(roleErrorKey(changeRole.error))}
        </p>
      )}

      {admins.isPending || superAdmins.isPending ? (
        <p className="py-6 text-muted">{t('admins.loading')}</p>
      ) : admins.isError || superAdmins.isError ? (
        <ErrorNote
          message={t('admins.loadFailed')}
          onRetry={() => queryClient.invalidateQueries({ queryKey: listUsersQueryKey() })}
        />
      ) : (
        <table className="w-full border-collapse border-t border-line text-sm">
          <caption className="sr-only">{t('admins.caption')}</caption>
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
              <th scope="col" className="px-2 py-4 font-normal md:p-4">
                <span className="sr-only">{t('admins.action')}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {team.map((user) => {
              // The viewer's own row and the super admins (managed on the server) are locked.
              const isMe = user.id === me.id
              const locked = isMe || adminOutOfReach(user.role, me.role)
              return (
                <tr key={user.id} className="border-t border-line">
                  <th scope="row" className="px-2 py-4 text-left font-normal md:p-4">
                    <span className="grid">
                      <b className="font-semibold">{name(user)}</b>
                      <small className="mt-1 text-xs break-all text-muted">{user.email}</small>
                    </span>
                  </th>
                  <td className="px-2 py-4 md:p-4">{t(`roles.${user.role}`)}</td>
                  <td className="px-2 py-4 md:p-4">{t(`status.${user.status}`)}</td>
                  <td className="px-2 py-4 text-right md:p-4">
                    {locked ? (
                      <span className="text-xs text-muted">{t(isMe ? 'table.you' : 'admins.locked')}</span>
                    ) : (
                      <Button
                        variant="link"
                        size="inline"
                        disabled={saving === user.id}
                        aria-label={t('admins.revokeOf', { name: name(user) })}
                        onClick={() => {
                          // A disabled or unverified admin can only go back to client (the API
                          // refuses agent): the dialog offers what the API accepts, agent first.
                          const choices = REVOKE_TO.filter((role) => canGiveRole(role, user, me.role))
                          setPending({
                            change: { userId: user.id, name: name(user), from: user.role, to: choices[0] },
                            choices,
                          })
                        }}
                        className="min-h-11 text-xs"
                      >
                        {t('admins.revoke')}
                      </Button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}

      <section aria-labelledby="admins-grant" className="mt-12">
        <h2 id="admins-grant" className="mb-2 text-xl">
          {t('admins.grantTitle')}
        </h2>
        <p className="mb-4 max-w-[60ch] text-sm text-muted">{t('admins.grantIntro')}</p>
        <label className="sr-only" htmlFor="admins-search">
          {t('admins.searchLabel')}
        </label>
        <Input
          id="admins-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t('admins.searchPlaceholder')}
          className="md:max-w-[350px]"
        />
        {q.length >= 2 &&
          (foundClients.isPending || foundAgents.isPending ? (
            <p className="py-4 text-muted">{t('admins.searching')}</p>
          ) : foundClients.isError || foundAgents.isError ? (
            <ErrorNote
              message={t('loadFailed')}
              onRetry={() => {
                void foundClients.refetch()
                void foundAgents.refetch()
              }}
            />
          ) : candidates.length === 0 ? (
            <p className="py-4 text-muted">{t('admins.noMatch')}</p>
          ) : (
            <ul aria-label={t('admins.results')} className="m-0 mt-4 grid list-none gap-1 p-0">
              {candidates.map((user) => {
                // The same rule as the users page: a disabled account or an unverified email
                // stays a client, so the page says why instead of offering the role.
                const reason = canGiveRole('admin', user, me.role)
                  ? null
                  : user.status === 'disabled'
                    ? 'admins.cannot.disabled'
                    : 'admins.cannot.unverified'
                return (
                  <li key={user.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-line py-3">
                    <span className="grid">
                      <b className="font-semibold">{name(user)}</b>
                      <small className="mt-1 text-xs break-all text-muted">
                        {user.email} · {t(`roles.${user.role}`)}
                      </small>
                    </span>
                    {reason ? (
                      <small className="text-xs text-muted">{t(reason)}</small>
                    ) : (
                      <Button
                        variant="link"
                        size="inline"
                        disabled={saving === user.id}
                        aria-label={t('admins.grantOf', { name: name(user) })}
                        onClick={() =>
                          setPending({ change: { userId: user.id, name: name(user), from: user.role, to: 'admin' } })
                        }
                        className="min-h-11 text-xs"
                      >
                        {t('admins.grant')}
                      </Button>
                    )}
                  </li>
                )
              })}
            </ul>
          ))}
      </section>

      <aside aria-labelledby="admins-help" className="mt-12 max-w-[72ch] border border-line bg-ivory p-5">
        <h2 id="admins-help" className="mb-2 text-lg">
          {t('admins.help.title')}
        </h2>
        <p className="mb-4 text-sm text-muted">{t('admins.help.body')}</p>
        {COMMANDS.map(({ label, command }) => (
          <div key={command} className="mb-3">
            <p className="mb-1 text-xs text-muted">{t(label)}</p>
            <pre className="m-0 overflow-x-auto bg-white p-3 text-xs">
              <code>{command}</code>
            </pre>
          </div>
        ))}
      </aside>

      <RoleChangeDialog
        change={pending?.change ?? null}
        choices={pending?.choices}
        onCancel={() => setPending(null)}
        onConfirm={(change) => {
          setPending(null)
          changeRole.mutate({ path: { user_id: change.userId }, body: { role: change.to } })
        }}
      />
    </>
  )
}
