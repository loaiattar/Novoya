import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { BackofficeLayout } from '../../../components/organisms/BackofficeLayout'
import { AppShell } from '../../../components/templates/AppShell'
import { canOpen } from '../../../domain/auth/roles'

// The admin area: the overview, users, partners and their offers, the extras, the reviews,
// the advisors on the home page, the agency's activity and the import of a new DÉTOUR export. Admins only, like /admin/users
// in the API; the others go back to /wish before anything is requested.
export const Route = createFileRoute('/_authenticated/admin')({
  beforeLoad: ({ context }) => {
    if (!canOpen(context.me.role, 'admin')) throw redirect({ to: '/wish' })
  },
  component: AdminArea,
})

function AdminArea() {
  const { t } = useTranslation('admin')
  const { me } = Route.useRouteContext()
  return (
    <AppShell>
      <BackofficeLayout
        area={t('area')}
        items={[
          { label: t('nav.overview'), to: '/admin', exact: true },
          { label: t('nav.users'), to: '/admin/users' },
          // A super admin only: the page is refused to the others (admins/index.tsx).
          ...(canOpen(me.role, 'admins') ? [{ label: t('nav.admins'), to: '/admin/admins' as const }] : []),
          { label: t('nav.partners'), to: '/admin/partners' },
          { label: t('nav.extras'), to: '/admin/extras' },
          { label: t('nav.reviews'), to: '/admin/reviews' },
          { label: t('nav.advisors'), to: '/admin/advisors' },
          { label: t('nav.activity'), to: '/admin/activity' },
          { label: t('nav.import'), to: '/admin/import' },
        ]}
      >
        <Outlet />
      </BackofficeLayout>
    </AppShell>
  )
}
