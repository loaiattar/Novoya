import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useQueue } from '../../../api/agentPlans'
import { BackofficeLayout } from '../../../components/organisms/BackofficeLayout'
import { AppShell } from '../../../components/templates/AppShell'
import { canOpen } from '../../../domain/auth/roles'

// The agency area: the quote queue and the plans an agent took. Agents and admins only, like
// /agent/plans in the API; the others go back to /wish before anything is requested.
export const Route = createFileRoute('/_authenticated/agent')({
  beforeLoad: ({ context }) => {
    if (!canOpen(context.me.role, 'agent')) throw redirect({ to: '/wish' })
  },
  component: AgentArea,
})

function AgentArea() {
  const { t } = useTranslation('agent')
  const waiting = useQueue('unassigned')
  return (
    <AppShell>
      <BackofficeLayout
        area={t('area')}
        items={[
          { label: t('nav.queue'), to: '/agent', count: waiting.isError ? undefined : (waiting.data?.length ?? null) },
          { label: t('nav.files') },
          { label: t('nav.sent') },
          { label: t('nav.partners') },
        ]}
      >
        <Outlet />
      </BackofficeLayout>
    </AppShell>
  )
}
