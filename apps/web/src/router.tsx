import { QueryClient } from '@tanstack/react-query'
import { createRouter, type RouterHistory } from '@tanstack/react-router'

import { RouteError } from './routes/__root'
import { routeTree } from './routeTree.gen'

export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

/** The app's router. Tests pass their own query client and a memory history. */
export function createAppRouter(client: QueryClient, history?: RouterHistory) {
  return createRouter({
    routeTree,
    context: { queryClient: client },
    history,
    defaultPreload: 'intent',
    defaultErrorComponent: RouteError,
  })
}

export const router = createAppRouter(queryClient)

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
