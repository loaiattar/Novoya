import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import './client'
import { ApiError, isUnauthenticated, retryAfterSeconds, serverErrorKey } from './errors'
import { getMe } from './generated/sdk.gen'
import { client } from './generated/client.gen'

describe('retryAfterSeconds', () => {
  it('reads delay-seconds and ignores anything else', () => {
    expect(retryAfterSeconds('720')).toBe(720)
    expect(retryAfterSeconds(' 12 ')).toBe(12)
    expect(retryAfterSeconds('0')).toBeUndefined()
    expect(retryAfterSeconds('Wed, 21 Oct 2015 07:28:00 GMT')).toBeUndefined()
    expect(retryAfterSeconds(null)).toBeUndefined()
  })
})

describe('isUnauthenticated', () => {
  it('is true only for a 401 with the unauthenticated code', () => {
    expect(isUnauthenticated(new ApiError(401, 'unauthenticated', 'not signed in'))).toBe(true)
    expect(isUnauthenticated(new ApiError(401, 'invalid_credentials', 'wrong password'))).toBe(false)
    expect(isUnauthenticated(new ApiError(500, 'unauthenticated', 'odd'))).toBe(false)
    expect(isUnauthenticated({ code: 'unauthenticated' })).toBe(false)
    expect(isUnauthenticated(new TypeError('Failed to fetch'))).toBe(false)
  })
})

describe('serverErrorKey', () => {
  it('says the service is busy for 503 database_busy', () => {
    expect(serverErrorKey(new ApiError(503, 'database_busy', 'the database is busy', 2))).toBe(
      'databaseBusy',
    )
  })

  it('keeps the generic message for any other failure', () => {
    expect(serverErrorKey(new ApiError(503, 'email_not_sent', 'smtp down'))).toBe('serverUnreachable')
    expect(serverErrorKey(new ApiError(500, 'unknown', 'Internal Server Error'))).toBe('serverUnreachable')
    expect(serverErrorKey(new TypeError('Failed to fetch'))).toBe('serverUnreachable')
    expect(serverErrorKey(undefined)).toBe('serverUnreachable')
  })
})

describe('the API client', () => {
  beforeEach(() => client.setConfig({ baseUrl: 'http://api.test' }))
  afterEach(() => vi.restoreAllMocks())

  it('throws an ApiError with the status and code of the answer', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      Response.json({ code: 'unauthenticated', detail: 'not signed in' }, { status: 401 }),
    )

    const error = await getMe({ throwOnError: true }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 401, code: 'unauthenticated', message: 'not signed in' })
  })

  it('keeps a body that is not JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('Bad gateway', { status: 502 }))

    const error = await getMe({ throwOnError: true }).catch((e: unknown) => e)

    expect(error).toMatchObject({ status: 502, code: 'unknown', message: 'Bad gateway' })
  })

  it('keeps Retry-After seconds on a 429', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      Response.json(
        { code: 'too_many_requests', detail: 'try again in 720 seconds' },
        { status: 429, headers: { 'Retry-After': '720' } },
      ),
    )

    const error = await getMe({ throwOnError: true }).catch((e: unknown) => e)

    expect(error).toMatchObject({ status: 429, code: 'too_many_requests', retryAfterSeconds: 720 })
  })

  it('keeps Retry-After seconds on a 503 database_busy', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      Response.json(
        { code: 'database_busy', detail: 'the database is busy, try again' },
        { status: 503, headers: { 'Retry-After': '2' } },
      ),
    )

    const error = await getMe({ throwOnError: true }).catch((e: unknown) => e)

    expect(error).toMatchObject({ status: 503, code: 'database_busy', retryAfterSeconds: 2 })
    expect(serverErrorKey(error)).toBe('databaseBusy')
  })

  it('keeps a network error as it is', async () => {
    const failure = new TypeError('Failed to fetch')
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(failure)

    await expect(getMe({ throwOnError: true })).rejects.toBe(failure)
  })
})
