import { describe, expect, it } from 'vitest'

import { rateLimitMessage, waitFromRetryAfter } from './wait'

describe('waitFromRetryAfter', () => {
  it('keeps seconds under a minute', () => {
    expect(waitFromRetryAfter(1)).toEqual({ unit: 'seconds', count: 1 })
    expect(waitFromRetryAfter(12)).toEqual({ unit: 'seconds', count: 12 })
    expect(waitFromRetryAfter(59)).toEqual({ unit: 'seconds', count: 59 })
  })

  it('rounds to minutes from 60 seconds', () => {
    expect(waitFromRetryAfter(60)).toEqual({ unit: 'minutes', count: 1 })
    expect(waitFromRetryAfter(90)).toEqual({ unit: 'minutes', count: 2 })
    expect(waitFromRetryAfter(720)).toEqual({ unit: 'minutes', count: 12 })
  })

  it('is missing when Retry-After is unusable', () => {
    expect(waitFromRetryAfter(undefined)).toBeNull()
    expect(waitFromRetryAfter(0)).toBeNull()
    expect(waitFromRetryAfter(-3)).toBeNull()
    expect(waitFromRetryAfter(12.5)).toBeNull()
    expect(waitFromRetryAfter(Number.NaN)).toBeNull()
  })
})

describe('rateLimitMessage', () => {
  it('keeps the fallback without a wait', () => {
    expect(rateLimitMessage('wish.tooManyRequests', undefined)).toEqual({ key: 'wish.tooManyRequests' })
    expect(rateLimitMessage('answers.tooManyRequests', 0)).toEqual({ key: 'answers.tooManyRequests' })
  })

  it('names seconds or minutes when Retry-After is present', () => {
    expect(rateLimitMessage('wish.tooManyRequests', 12)).toEqual({
      key: 'rateLimit.waitSeconds',
      count: 12,
    })
    expect(rateLimitMessage('answers.tooManyRequests', 720)).toEqual({
      key: 'rateLimit.waitMinutes',
      count: 12,
    })
  })
})
