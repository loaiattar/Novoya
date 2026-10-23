import { rateLimitMessage } from '../rateLimit/wait'

/** The API's limit for a wish's text (SendWishRequest). */
export const WISH_MAX_LENGTH = 1000

// Texts in errors.json under wish.<key>; the page passes { max: WISH_MAX_LENGTH } for tooLong.
export type WishTextErrorKey = 'wish.empty' | 'wish.tooLong'
export type SendWishErrorKey = 'wish.invalid' | 'wish.tooManyRequests' | 'wish.unknown'

/** Why the wish cannot be sent yet, or null when it can. */
export function wishTextError(text: string): WishTextErrorKey | null {
  const trimmed = text.trim()
  if (!trimmed) return 'wish.empty'
  if (trimmed.length > WISH_MAX_LENGTH) return 'wish.tooLong'
  return null
}

/** The key of the message for a wish the API refused. */
export function sendWishErrorKey(code: string | undefined): SendWishErrorKey {
  if (code === 'invalid_wish') return 'wish.invalid'
  if (code === 'too_many_requests' || code === 'too_many_attempts') return 'wish.tooManyRequests'
  return 'wish.unknown'
}

/** The message for a refused wish, with a wait when Retry-After is present. */
export function sendWishError(
  code: string | undefined,
  retryAfterSeconds?: number,
): { key: SendWishErrorKey | 'rateLimit.waitSeconds' | 'rateLimit.waitMinutes'; count?: number } {
  const key = sendWishErrorKey(code)
  return key === 'wish.tooManyRequests' ? rateLimitMessage(key, retryAfterSeconds) : { key }
}
