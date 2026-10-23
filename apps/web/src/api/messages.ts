import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { listWishMessagesOptions, listWishMessagesQueryKey } from './generated/@tanstack/react-query.gen'
import { postWishMessage } from './generated/sdk.gen'

/** How often an open conversation asks for new messages. Polling is enough for now (#169). */
export const CHAT_POLL_MS = 5_000

/**
 * The advisor chat of a wish, GET /wishes/{id}/messages, read again every few seconds while
 * `open` (the chat window is open, or the agent's page shows it) and the tab is visible.
 */
export function useWishMessages(wishId: string, open: boolean) {
  return useQuery({
    ...listWishMessagesOptions({ path: { wish_id: wishId } }),
    enabled: open,
    refetchInterval: open ? CHAT_POLL_MS : false,
    refetchIntervalInBackground: false,
    retry: false,
  })
}

/** Write in the chat with POST /wishes/{id}/messages, then read the conversation again. */
export function usePostMessage(wishId: string) {
  const queryClient = useQueryClient()
  const queryKey = listWishMessagesQueryKey({ path: { wish_id: wishId } })
  return useMutation({
    mutationFn: async (body: string) => {
      const { data } = await postWishMessage({ path: { wish_id: wishId }, body: { body }, throwOnError: true })
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  })
}
