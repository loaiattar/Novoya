import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { ApiError, isUnauthenticated } from './errors'
import {
  getMeQueryKey,
  getPlanOptions,
  getPlanQueryKey,
  listMyTripsQueryKey,
} from './generated/@tanstack/react-query.gen'
import { requestQuote } from './generated/sdk.gen'

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

/**
 * Send the plan to the agency with POST /plans/{id}/request-quote. Success or not, the plan
 * and My trips are read again: a 409 means it was sent already (a second tab, a double click),
 * and the page then shows it as sent. The API sends the confirmation email only once.
 * A 401 means the session ended: sign in again and come back to `comeBackTo`, as usePlan does.
 */
export function useSendToAgency(planId: string, comeBackTo: string) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data } = await requestQuote({ path: { plan_id: planId }, throwOnError: true })
      return data
    },
    onSuccess: (plan) => queryClient.setQueryData(getPlanQueryKey({ path: { plan_id: planId } }), plan),
    onError: (error) => {
      if (!isUnauthenticated(error)) return
      queryClient.removeQueries({ queryKey: getMeQueryKey() })
      void navigate({ to: '/login', search: { redirect: comeBackTo }, replace: true })
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getPlanQueryKey({ path: { plan_id: planId } }) }),
        queryClient.invalidateQueries({ queryKey: listMyTripsQueryKey() }),
      ])
    },
  })
}
