import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { isUnauthenticated } from './errors'
import { getMeQueryKey, listMyTripsOptions } from './generated/@tanstack/react-query.gen'

/**
 * The client's trips, read with GET /me/trips. `comeBackTo` is where to come back after
 * signing in again if the session ended.
 */
export function useMyTrips(comeBackTo: string) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const trips = useQuery({ ...listMyTripsOptions(), retry: false })
  const signedOut = isUnauthenticated(trips.error)

  // Same as the quote page: drop the cached /me first, then sign in again and come back.
  useEffect(() => {
    if (!signedOut) return
    queryClient.removeQueries({ queryKey: getMeQueryKey() })
    void navigate({ to: '/login', search: { redirect: comeBackTo }, replace: true })
  }, [signedOut, queryClient, navigate, comeBackTo])

  return { trips, signedOut }
}
