import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { BackofficeLayout } from '../../../components/organisms/BackofficeLayout'
import { AppShell } from '../../../components/templates/AppShell'
import { canOpen } from '../../../domain/auth/roles'

// The admin area: users, partners and their offers, the extras, the reviews and the agency's
// activity. Admins only, like /admin/users in the API; the others go back to /wish before
// anything is requested.
export const Route = createFileRoute('/_authenticated/admin')({
  beforeLoad: ({ context }) => {
    if (!canOpen(context.me.role, 'admin')) throw redirect({ to: '/wish' })
  },
  component: AdminArea,
})

function AdminArea() {
  const { t } = useTranslation('admin')
  return (
    <AppShell>
      <BackofficeLayout
        area={t('area')}
        items={[
          { label: t('nav.users'), to: '/admin', exact: true },
          { label: t('nav.partners'), to: '/admin/partners' },
          { label: t('nav.extras'), to: '/admin/extras' },
          { label: t('nav.reviews'), to: '/admin/reviews' },
          { label: t('nav.activity'), to: '/admin/activity' },
        ]}
      >
        <Outlet />
      </BackofficeLayout>
    </AppShell>
  )
}
