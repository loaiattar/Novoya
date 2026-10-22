import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { type ReactNode, useDeferredValue, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  listAdminPlansOptions,
  listAdminQuotesOptions,
  listAdminWishesOptions,
} from '../../../../api/generated/@tanstack/react-query.gen'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { ActivityFilters } from '../../../../components/molecules/ActivityFilters'
import { ErrorNote } from '../../../../components/molecules/ErrorNote'
import { lineTabList, lineTabPanel, lineTabTrigger } from '../../../../components/molecules/lineTabs'
import { AdminPlansTable } from '../../../../components/organisms/AdminPlansTable'
import { AdminQuotesTable } from '../../../../components/organisms/AdminQuotesTable'
import { AdminWishesTable } from '../../../../components/organisms/AdminWishesTable'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../../components/ui/tabs'
import {
  ACTIVITY_TABS,
  type ActivityTab,
  PLAN_STATUSES,
  type PlanStatus,
  QUOTE_STATUSES,
  type QuoteStatus,
  WISH_STATUSES,
  type WishStatus,
} from '../../../../domain/admin/activity'

type ActivitySearch = {
  tab?: ActivityTab
  /** Only the plans of this wish, from the wishes tab. */
  wish?: string
}

// The guard is in ../route.tsx: admins only. The tab is in the URL, so a link can open one.
export const Route = createFileRoute('/_authenticated/admin/activity/')({
  validateSearch: (search: Record<string, unknown>): ActivitySearch => ({
    tab: ACTIVITY_TABS.find((tab) => tab === search.tab),
    wish: typeof search.wish === 'string' ? search.wish : undefined,
  }),
  component: ActivityPage,
})

const PAGE = 50

/** Every wish, plan and quote of every client, one tab each, searched on the server. */
function ActivityPage() {
  const { t } = useTranslation('admin')
  const { tab = 'wishes', wish } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })

  return (
    <>
      <Eyebrow>{t('eyebrow')}</Eyebrow>
      <h1 className="m-0 text-[39px] md:text-[50px]">{t('activity.title')}</h1>
      <p className="mt-3 max-w-[60ch] text-muted">{t('activity.intro')}</p>
      <Tabs
        value={tab}
        onValueChange={(value) => navigate({ search: { tab: value as ActivityTab } })}
        className="mt-8"
      >
        <TabsList className={`${lineTabList} gap-2.5`}>
          {ACTIVITY_TABS.map((value) => (
            <TabsTrigger key={value} value={value} className={`${lineTabTrigger} px-3.5`}>
              {t(`activity.tabs.${value}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="wishes" className={lineTabPanel}>
          <WishesTab />
        </TabsContent>
        <TabsContent value="plans" className={lineTabPanel}>
          <PlansTab wishId={wish} />
        </TabsContent>
        <TabsContent value="quotes" className={lineTabPanel}>
          <QuotesTab />
        </TabsContent>
      </Tabs>
    </>
  )
}

/** The search sent to the API once the admin stops typing, and the status filter. */
function useFilters<S extends string>() {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<S | ''>('')
  const q = useDeferredValue(search.trim())
  return { search, setSearch, status, setStatus, query: { q: q || undefined, status: status || undefined, limit: PAGE } }
}

function WishesTab() {
  const { t } = useTranslation('admin')
  const filters = useFilters<WishStatus>()
  const wishes = useQuery({ ...listAdminWishesOptions({ query: filters.query }), placeholderData: keepPreviousData })
  return (
    <>
      <ActivityFilters
        search={filters.search}
        onSearch={filters.setSearch}
        status={filters.status}
        statuses={WISH_STATUSES}
        statusLabel={(status) => t(`activity.wishStatus.${status}`)}
        onStatus={filters.setStatus}
      />
      <ListState query={wishes}>{(rows) => <AdminWishesTable wishes={rows} />}</ListState>
    </>
  )
}

function PlansTab({ wishId }: { wishId?: string }) {
  const { t } = useTranslation('admin')
  const filters = useFilters<PlanStatus>()
  const plans = useQuery({
    ...listAdminPlansOptions({ query: { ...filters.query, wish_id: wishId } }),
    placeholderData: keepPreviousData,
  })
  return (
    <>
      <ActivityFilters
        search={filters.search}
        onSearch={filters.setSearch}
        status={filters.status}
        statuses={PLAN_STATUSES}
        statusLabel={(status) => t(`activity.planStatus.${status}`)}
        onStatus={filters.setStatus}
      />
      {wishId && (
        <p className="mb-4 flex flex-wrap items-center gap-x-3 text-sm">
          {t('activity.plans.ofWish')}
          <Link to="/admin/activity" search={{ tab: 'plans' }} className="inline-flex min-h-11 items-center underline underline-offset-4">
            {t('activity.plans.allPlans')}
          </Link>
        </p>
      )}
      <ListState query={plans}>{(rows) => <AdminPlansTable plans={rows} />}</ListState>
    </>
  )
}

function QuotesTab() {
  const { t } = useTranslation('admin')
  const filters = useFilters<QuoteStatus>()
  const quotes = useQuery({ ...listAdminQuotesOptions({ query: filters.query }), placeholderData: keepPreviousData })
  return (
    <>
      <ActivityFilters
        search={filters.search}
        onSearch={filters.setSearch}
        status={filters.status}
        statuses={QUOTE_STATUSES}
        statusLabel={(status) => t(`activity.quoteStatus.${status}`)}
        onStatus={filters.setStatus}
      />
      <ListState query={quotes}>{(rows) => <AdminQuotesTable quotes={rows} />}</ListState>
    </>
  )
}

type ListQuery<T> = { isPending: boolean; isError: boolean; data: T[] | undefined; refetch: () => unknown }

/** Loading, failed, empty, or the table: the same states as the users page. */
function ListState<T>({ query, children }: { query: ListQuery<T>; children: (rows: T[]) => ReactNode }) {
  const { t } = useTranslation('admin')
  if (query.isPending) return <p className="py-6 text-muted">{t('activity.loading')}</p>
  if (query.isError || !query.data) return <ErrorNote message={t('activity.loadFailed')} onRetry={() => query.refetch()} />
  if (query.data.length === 0) return <p className="py-6 text-muted">{t('activity.empty')}</p>
  return <div className="overflow-x-auto">{children(query.data)}</div>
}
