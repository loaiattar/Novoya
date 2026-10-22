/** An error answered by the API: its HTTP status and the `code` of its ErrorResponse body. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  /** Seconds from Retry-After, when the API sent a delay-seconds value. */
  readonly retryAfterSeconds?: number

  constructor(status: number, code: string, detail: string, retryAfterSeconds?: number) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.retryAfterSeconds = retryAfterSeconds
  }
}

/** Delay-seconds from Retry-After. HTTP-dates and anything else are ignored. */
export function retryAfterSeconds(header: string | null): number | undefined {
  if (!header) return undefined
  const trimmed = header.trim()
  if (!/^[0-9]+$/.test(trimmed)) return undefined
  const seconds = Number(trimmed)
  return seconds >= 1 ? seconds : undefined
}

/**
 * Turns the body the generated client throws into an ApiError, with the response's status.
 * A network or CORS failure has no response: its error is kept as it is.
 */
export function toApiError(body: unknown, response: Response | undefined): unknown {
  if (!response) return body
  const { code, detail } = (typeof body === 'object' && body !== null ? body : {}) as {
    code?: unknown
    detail?: unknown
  }
  return new ApiError(
    response.status,
    typeof code === 'string' ? code : 'unknown',
    typeof detail === 'string' ? detail : typeof body === 'string' ? body : response.statusText,
    retryAfterSeconds(response.headers.get('Retry-After')),
  )
}

/** No session, or it expired or was revoked: the only error that means "go to /login". */
export function isUnauthenticated(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401 && error.code === 'unauthenticated'
}
