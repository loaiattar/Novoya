function firstWord(value: string | null | undefined): string | undefined {
  const word = value?.trim().split(/\s+/)[0]
  return word || undefined
}

/** First name, or the first word of the stored name. Old accounts may have only `name`. */
export function givenName(user: {
  first_name: string | null
  name?: string | null
}): string | undefined {
  return firstWord(user.first_name) ?? firstWord(user.name)
}

/** The name to show in the header. Without a given name, fall back to the email. */
export function displayName(user: {
  first_name: string | null
  name?: string | null
  email: string
}): string {
  return givenName(user) || user.email
}

// oxlint-disable-next-line no-control-regex -- rejecting control characters is the point
const CONTROL = /[\x00-\x1f\x7f]/
const MAX_LENGTH = 512 // RedirectPolicy.max_length and the oauth_states.redirect_to column

/**
 * A page of the web app to go to after signing in, or `fallback`.
 * Same rule as the API's RedirectPolicy: a relative path, never another site.
 */
export function safeRedirect(target: unknown, fallback = '/'): string {
  if (typeof target !== 'string' || !target || target.length > MAX_LENGTH) return fallback
  if (!target.startsWith('/') || target.startsWith('//') || target.startsWith('/\\')) return fallback
  if (CONTROL.test(target)) return fallback
  return target
}
