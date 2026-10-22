import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { client } from './generated/client.gen'
import { ApiError, isUnauthenticated } from './errors'
import { getMeQueryKey, getQuoteOptions, getQuoteQueryKey } from './generated/@tanstack/react-query.gen'
import { acceptQuote, rejectQuote } from './generated/sdk.gen'

/**
 * The quote read with GET /quotes/{id}, for the client's quote page.
 * `comeBackTo` is where to come back after signing in again if the session ended.
 */
export function useQuote(quoteId: string, comeBackTo: string) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const quote = useQuery({ ...getQuoteOptions({ path: { quote_id: quoteId } }), retry: false })
  const signedOut = isUnauthenticated(quote.error)

  // Same as the plan page: drop the cached /me first, then sign in again and come back.
  useEffect(() => {
    if (!signedOut) return
    queryClient.removeQueries({ queryKey: getMeQueryKey() })
    void navigate({ to: '/login', search: { redirect: comeBackTo }, replace: true })
  }, [signedOut, queryClient, navigate, comeBackTo])

  // 404: not the caller's quote, or no such quote. 422: the id is not even a quote id.
  const missing = quote.error instanceof ApiError && [404, 422].includes(quote.error.status)

  return { quote, signedOut, missing }
}

export type Answer = 'accept' | 'reject'

/**
 * Accept or reject the quote with POST /quotes/{id}/accept or /reject. After it, success or
 * not, the quote is read again: a 409 means it expired or was answered meanwhile, and the
 * page then shows that.
 */
export function useAnswerQuote(quoteId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ answer, comment }: { answer: Answer; comment: string }) => {
      const send = answer === 'accept' ? acceptQuote : rejectQuote
      await send({
        path: { quote_id: quoteId },
        body: { comment: comment.trim() || null },
        throwOnError: true,
      })
    },
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: getQuoteQueryKey({ path: { quote_id: quoteId } }) }),
  })
}

/** Where the browser downloads the quote PDF, with the session cookie. */
export function quotePdfUrl(quoteId: string): string {
  return `${client.getConfig().baseUrl ?? ''}/quotes/${encodeURIComponent(quoteId)}/pdf`
}
