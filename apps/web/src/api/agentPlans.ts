import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { ApiError, isUnauthenticated } from './errors'
import {
  getAgentPlanOptions,
  getMeQueryKey,
  getPlanQuoteOptions,
  listQuoteQueueOptions,
} from './generated/@tanstack/react-query.gen'
import type { ListQuoteQueueData } from './generated/types.gen'

export type QueueFilter = 'unassigned' | 'in_progress' | 'decided'
type QueueStatus = NonNullable<NonNullable<ListQuoteQueueData['query']>['status']>[number]

/** The statuses behind each tab of the queue. Past "requested", the API lists only my plans. */
export const QUEUE_STATUSES: Record<QueueFilter, QueueStatus[]> = {
  unassigned: ['requested'],
  in_progress: ['negotiating'],
  decided: ['quoted', 'accepted', 'rejected'],
}

/** The most the API gives in one page (QUEUE_CAP). Paging is not there yet. */
export const QUEUE_LIMIT = 100

/** The queue options for one tab, also used to read it again after a take. */
export const queueOptions = (filter: QueueFilter) =>
  listQuoteQueueOptions({ query: { status: QUEUE_STATUSES[filter], limit: QUEUE_LIMIT } })

/** One tab of the agency queue, oldest first. */
export function useQueue(filter: QueueFilter) {
  return useQuery(queueOptions(filter))
}

/**
 * The plan as its agent sees it (GET /agent/plans/{id}): prices, partners, total vs budget.
 * `comeBackTo` is where to come back after signing in again if the session ended.
 */
export function useAgentPlan(planId: string, comeBackTo: string) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const plan = useQuery({ ...getAgentPlanOptions({ path: { plan_id: planId } }), retry: false })
  const signedOut = isUnauthenticated(plan.error)

  // As in usePlan: the cached /me goes first, or the sign-in page would send the agent back.
  useEffect(() => {
    if (!signedOut) return
    queryClient.removeQueries({ queryKey: getMeQueryKey() })
    void navigate({ to: '/login', search: { redirect: comeBackTo }, replace: true })
  }, [signedOut, queryClient, navigate, comeBackTo])

  // 403: another agent took it. 404: no such plan. 422: not even a plan id.
  const missing = plan.error instanceof ApiError && [403, 404, 422].includes(plan.error.status)

  return { plan, signedOut, missing }
}

/** The quote sent for a plan, read once the plan is quoted (404 before that). */
export function usePlanQuote(planId: string, enabled: boolean) {
  return useQuery({ ...getPlanQuoteOptions({ path: { plan_id: planId } }), enabled, retry: false })
}
