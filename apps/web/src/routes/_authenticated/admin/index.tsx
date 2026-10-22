import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { getAdminStatsOptions } from '../../../api/generated/@tanstack/react-query.gen'
import type { AdminStatsResponse, StatsRows } from '../../../api/generated/types.gen'
import { Eyebrow } from '../../../components/atoms/Eyebrow'
import { ErrorNote } from '../../../components/molecules/ErrorNote'
import { StatTile } from '../../../components/molecules/StatTile'

// The guard is in route.tsx: admins only.
export const Route = createFileRoute('/_authenticated/admin/')({
  component: DashboardPage,
})

/** The admin home: the agency's key numbers, each one opening its page. Counts only. */
function DashboardPage() {
  const { t } = useTranslation('admin')
  // Read again on every visit: the numbers must show what the admin just changed on the
  // other pages, and the router keeps a query fresh for 30 seconds by default.
  const stats = useQuery({ ...getAdminStatsOptions(), staleTime: 0 })

  return (
    <>
      <Eyebrow>{t('eyebrow')}</Eyebrow>
      <h1 className="m-0 text-[39px] md:text-[50px]">{t('dashboard.title')}</h1>
      <p className="mt-3 mb-8 max-w-[60ch] text-muted">{t('dashboard.intro')}</p>
      {stats.isPending ? (
        <p className="py-6 text-muted">{t('dashboard.loading')}</p>
      ) : !stats.data ? (
        <ErrorNote message={t('dashboard.loadFailed')} onRetry={() => stats.refetch()} />
      ) : (
        <Numbers stats={stats.data} />
      )}
    </>
  )
}

function Numbers({ stats }: { stats: AdminStatsResponse }) {
  const { t } = useTranslation('admin')
  const { plans, quotes, users } = stats
  // What a catalog number leaves out: the rows an admin hid, and those DÉTOUR no longer exports.
  // Offers have their own texts: in French, the words agree with "offre".
  const leftOut = (rows: StatsRows, offers = false) => [
    offers ? t('dashboard.offersHidden', { count: rows.hidden }) : t('dashboard.hidden', { count: rows.hidden }),
    ...(rows.inactive === 0
      ? []
      : [
          offers
            ? t('dashboard.offersInactive', { count: rows.inactive })
            : t('dashboard.inactive', { count: rows.inactive }),
        ]),
  ]
  const toPlans = (content: ReactNode, className: string) => (
    <Link to="/admin/activity" search={{ tab: 'plans' }} className={className}>
      {content}
    </Link>
  )
  const toQuotes = (content: ReactNode, className: string) => (
    <Link to="/admin/activity" search={{ tab: 'quotes' }} className={className}>
      {content}
    </Link>
  )
  const toPartners = (content: ReactNode, className: string) => (
    <Link to="/admin/partners" className={className}>
      {content}
    </Link>
  )

  return (
    <div className="grid gap-10">
      <Section title={t('dashboard.sections.work')}>
        <StatTile
          label={t('dashboard.waiting')}
          value={plans.requested}
          details={[t('dashboard.waitingDetail', { count: plans.negotiating })]}
          renderLink={toPlans}
        />
        <StatTile label={t('dashboard.openQuotes')} value={quotes.open} renderLink={toQuotes} />
        <StatTile label={t('dashboard.expiredQuotes')} value={quotes.expired} renderLink={toQuotes} />
        <StatTile
          label={t('dashboard.answered')}
          value={quotes.accepted}
          details={[t('dashboard.rejected', { count: quotes.rejected })]}
          renderLink={toQuotes}
        />
      </Section>
      <Section title={t('dashboard.sections.catalog')}>
        <StatTile
          label={t('dashboard.partners')}
          value={stats.partners.active}
          details={leftOut(stats.partners)}
          renderLink={toPartners}
        />
        <StatTile
          label={t('dashboard.offers')}
          value={stats.offers.active}
          details={leftOut(stats.offers, true)}
          renderLink={toPartners}
        />
        <StatTile
          label={t('dashboard.extras')}
          value={stats.extras.active}
          details={leftOut(stats.extras)}
          renderLink={(content, className) => (
            <Link to="/admin/extras" className={className}>
              {content}
            </Link>
          )}
        />
        <StatTile
          label={t('dashboard.reviews')}
          value={stats.reviews.published}
          details={[t('dashboard.hidden', { count: stats.reviews.hidden })]}
          renderLink={(content, className) => (
            <Link to="/admin/reviews" className={className}>
              {content}
            </Link>
          )}
        />
      </Section>
      <Section title={t('dashboard.sections.accounts')}>
        <StatTile
          label={t('dashboard.users')}
          value={users.client + users.agent + users.admin + users.super_admin}
          details={[
            t('dashboard.byRole', { client: users.client, agent: users.agent, admin: users.admin + users.super_admin }),
          ]}
          renderLink={(content, className) => (
            <Link to="/admin/users" className={className}>
              {content}
            </Link>
          )}
        />
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title}>
      <h2 className="mb-4 text-xs font-normal tracking-widest text-muted uppercase">{title}</h2>
      <ul className="m-0 grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2 lg:grid-cols-4">{children}</ul>
    </section>
  )
}
