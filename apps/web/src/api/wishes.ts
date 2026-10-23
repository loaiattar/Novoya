import { useQuery } from '@tanstack/react-query'

import { getPanelLimitsOptions } from './generated/@tanstack/react-query.gen'
import type { WishResponse } from './generated/types.gen'

/** A wish answered by POST /wishes, with the text the client wrote (the response does not repeat it). */
export type CachedWish = WishResponse & { text: string }

/**
 * Where the wish answered by POST /wishes is kept for the preferences page.
 * There is no GET /wishes/{id} yet, so after a reload the page cannot find it again.
 */
export const wishQueryKey = (wishId: string) => ['wish', wishId] as const

export type { WishResponse }

/**
 * What the panel may offer, read from the catalog when it opens (GET /wishes/{id}/limits, #183).
 * With `check` (travellers and both dates), also whether at least one offer fits them. A failed
 * read is not retried: the panel then keeps its usual bounds, and the answer still checks.
 */
export function usePanelLimits(wishId: string, check?: { persons: number; startDate: string; endDate: string }) {
  const query = check ? { persons: check.persons, start_date: check.startDate, end_date: check.endDate } : undefined
  // Never from the cache: the API says no-store, and an offer added meanwhile must count.
  return useQuery({ ...getPanelLimitsOptions({ path: { wish_id: wishId }, query }), retry: false, staleTime: 0 })
}
