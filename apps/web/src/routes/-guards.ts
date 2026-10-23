import type { QueryClient } from '@tanstack/react-query'
import { redirect } from '@tanstack/react-router'

import { isUnauthenticated } from '../api/errors'
import { getMeOptions } from '../api/generated/@tanstack/react-query.gen'

/**
 * For the sign-in and sign-up pages: shown only when there is no session. Already signed in,
 * go to `target`. Any other failure is rethrown, so an API outage does not look like being
 * signed out.
 */
export async function redirectIfSignedIn(queryClient: QueryClient, target: string): Promise<void> {
  try {
    await queryClient.ensureQueryData({ ...getMeOptions(), retry: false })
  } catch (error) {
    if (isUnauthenticated(error)) return
    throw error
  }
  throw redirect({ href: target })
}
