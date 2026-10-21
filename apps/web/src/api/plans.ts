import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { ApiError, isUnauthenticated } from './errors'
import { getMeQueryKey, getPlanOptions } from './generated/@tanstack/react-query.gen'

/**
 * The plan read with GET /plans/{id}, for the plan page and its day pages: one query, so
 * opening a day from the plan reads it from the cache.
 * `comeBackTo` is where to come back after signing in again if the session ended.
 */
export function usePlan(planId: string, comeBackTo: string) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const plan = useQuery({ ...getPlanOptions({ path: { plan_id: planId } }), retry: false })
  const signedOut = isUnauthenticated(plan.error)

  // The session ended while on the page: sign in again and come back here. The cached /me
  // goes first, or the sign-in page would see a session and send the client straight back.
  // The way back is built by the caller, not from the current location: that one turns into
  // /login while navigating, and would nest redirect after redirect.
  useEffect(() => {
    if (!signedOut) return
    queryClient.removeQueries({ queryKey: getMeQueryKey() })
    void navigate({ to: '/login', search: { redirect: comeBackTo }, replace: true })
  }, [signedOut, queryClient, navigate, comeBackTo])

  // 404: not the caller's plan, or no such plan. 403: not a client (an agent, an admin).
  // 422: the id is not even a plan id. Trying again would never change these.
  const missing = plan.error instanceof ApiError && [403, 404, 422].includes(plan.error.status)

  return { plan, signedOut, missing }
}
