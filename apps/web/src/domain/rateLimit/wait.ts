/** How long to wait, in a unit that reads well. */
export type Wait = { unit: 'seconds' | 'minutes'; count: number }

/**
 * Turns Retry-After seconds into a wait that a sentence can use. Under a minute stays in
 * seconds; from 60 s it becomes minutes, rounded. Nothing usable (missing, 0, not a
 * number) is null: the caller keeps today's "wait a moment" message.
 */
export function waitFromRetryAfter(seconds: number | undefined): Wait | null {
  if (seconds === undefined || !Number.isInteger(seconds) || seconds < 1) return null
  if (seconds < 60) return { unit: 'seconds', count: seconds }
  return { unit: 'minutes', count: Math.max(1, Math.round(seconds / 60)) }
}

/** The i18n key and count for a 429, or the fallback when Retry-After is missing. */
export function rateLimitMessage<K extends 'wish.tooManyRequests' | 'answers.tooManyRequests'>(
  fallbackKey: K,
  seconds: number | undefined,
): { key: K | 'rateLimit.waitSeconds' | 'rateLimit.waitMinutes'; count?: number } {
  const wait = waitFromRetryAfter(seconds)
  if (!wait) return { key: fallbackKey }
  return {
    key: wait.unit === 'seconds' ? 'rateLimit.waitSeconds' : 'rateLimit.waitMinutes',
    count: wait.count,
  }
}
