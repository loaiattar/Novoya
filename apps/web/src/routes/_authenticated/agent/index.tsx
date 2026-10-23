import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { QUEUE_LIMIT, queueOptions, useQueue, type QueueFilter } from '../../../api/agentPlans'
import { ApiError } from '../../../api/errors'
import { getAgentPlanQueryKey, takePlanMutation } from '../../../api/generated/@tanstack/react-query.gen'
import { Eyebrow } from '../../../components/atoms/Eyebrow'
import { ErrorNote } from '../../../components/molecules/ErrorNote'
import { lineTabList, lineTabPanel, lineTabTrigger } from '../../../components/molecules/lineTabs'
import { RequestRow } from '../../../components/organisms/RequestRow'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../components/ui/tabs'

export const Route = createFileRoute('/_authenticated/agent/')({
  component: QueuePage,
})

const FILTERS: QueueFilter[] = ['unassigned', 'in_progress', 'decided']

// A full page may not be all of it: say "100+" rather than a count that looks exact.
const countOf = (entries: unknown[] | undefined) =>
  entries === undefined ? '0' : entries.length >= QUEUE_LIMIT ? `${QUEUE_LIMIT}+` : String(entries.length)

/** The plans waiting for an agent, and the ones this agent took, from GET /agent/plans. */
function QueuePage() {
  const { t } = useTranslation('agent')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const queues = { unassigned: useQueue('unassigned'), in_progress: useQueue('in_progress'), decided: useQueue('decided') }
  const [takeError, setTakeError] = useState<string | null>(null)

  const take = useMutation({
    ...takePlanMutation(),
    onSuccess: (plan) => {
      queryClient.setQueryData(getAgentPlanQueryKey({ path: { plan_id: plan.id } }), plan)
      void queryClient.invalidateQueries({ queryKey: queueOptions('unassigned').queryKey })
      void queryClient.invalidateQueries({ queryKey: queueOptions('in_progress').queryKey })
      void navigate({ to: '/agent/plans/$planId', params: { planId: plan.id } })
    },
    onError: (error) => {
      // 409: another agent was quicker. The queue is read again so the plan leaves it.
      setTakeError(error instanceof ApiError && error.status === 409 ? t('request.taken') : t('request.takeFailed'))
      void queryClient.invalidateQueries({ queryKey: queueOptions('unassigned').queryKey })
    },
  })

  const onTake = (planId: string) => {
    // One plan at a time: a second click elsewhere would take that plan too.
    if (take.isPending) return
    setTakeError(null)
    take.mutate({ path: { plan_id: planId } })
  }

  return (
    <>
      <div className="flex items-end justify-between gap-4">
        <div>
          <Eyebrow>{t('eyebrow')}</Eyebrow>
          <h1 className="m-0 text-display-s">{t('title')}</h1>
        </div>
        {/* Kept in place while loading, so the title does not wrap when the count arrives. */}
        <p className={`m-0 flex items-center gap-2 ${queues.unassigned.data ? '' : 'invisible'}`}>
          <span className="font-serif text-[32px]">{countOf(queues.unassigned.data)}</span>
          <small className="text-muted">{t('toTake')}</small>
        </p>
      </div>
      {takeError && (
        <p role="alert" className="mt-6 text-danger">
          {takeError}
        </p>
      )}
      <Tabs defaultValue="unassigned" className="mt-10">
        <TabsList className={`${lineTabList} gap-2.5`}>
          {FILTERS.map((filter) => (
            <TabsTrigger key={filter} value={filter} className={`${lineTabTrigger} px-3.5`}>
              {t('filterTab', { label: t(`filters.${filter}`), count: countOf(queues[filter].data) })}
            </TabsTrigger>
          ))}
        </TabsList>
        {FILTERS.map((filter) => {
          const queue = queues[filter]
          return (
            <TabsContent key={filter} value={filter} className={`${lineTabPanel} min-h-80`}>
              {queue.isPending ? (
                <p className="py-8 text-muted">{t('loading')}</p>
              ) : queue.isError && !queue.data ? (
                <ErrorNote message={t('loadFailed')} onRetry={() => queue.refetch()} />
              ) : queue.data.length === 0 ? (
                <p className="py-8 text-muted">{t('empty')}</p>
              ) : (
                queue.data.map((entry) => (
                  <RequestRow
                    key={entry.id}
                    entry={entry}
                    onTake={filter === 'unassigned' ? () => onTake(entry.id) : undefined}
                    taking={take.isPending}
                  />
                ))
              )}
            </TabsContent>
          )
        })}
      </Tabs>
    </>
  )
}
