// The codes the API puts in /login?error=<code> when a Google sign-in fails.
// Their texts are in i18n/locales/<language>/errors.json, under signIn.<code>.
const SIGN_IN_ERROR_CODES = [
  'oauth_cancelled',
  'oauth_failed',
  'oauth_state_invalid',
  'oauth_email_not_verified',
  'oauth_link_not_allowed',
  'identity_already_linked',
  'account_disabled',
  'user_not_found',
  'too_many_attempts',
  'unknown_provider',
] as const

type SignInErrorCode = (typeof SIGN_IN_ERROR_CODES)[number]
export type SignInErrorKey = `signIn.${SignInErrorCode | 'unknown'}`

const KNOWN = new Set<string>(SIGN_IN_ERROR_CODES)

/** The key of the message to show for a sign-in error code, or null when there is no error. */
export function signInErrorKey(code: string | undefined): SignInErrorKey | null {
  if (!code) return null
  return KNOWN.has(code) ? (`signIn.${code}` as SignInErrorKey) : 'signIn.unknown'
}

// The codes POST /auth/login answers with when an e-mail and password sign-in fails.
// Their texts are in errors.json, under password.<code>.
const PASSWORD_ERROR_CODES = [
  'invalid_credentials',
  'email_not_verified',
  'no_password_set',
  'account_disabled',
  'too_many_attempts',
] as const

type PasswordErrorCode = (typeof PASSWORD_ERROR_CODES)[number]
export type PasswordSignInErrorKey = `password.${PasswordErrorCode | 'unknown'}`

const KNOWN_PASSWORD = new Set<string>(PASSWORD_ERROR_CODES)

/** The key of the message for a failed e-mail and password sign-in. */
export function passwordSignInErrorKey(code: string | undefined): PasswordSignInErrorKey {
  // The rate limiter answers too_many_requests; it reads the same as too_many_attempts.
  if (code === 'too_many_requests') return 'password.too_many_attempts'
  return code && KNOWN_PASSWORD.has(code) ? (`password.${code}` as PasswordSignInErrorKey) : 'password.unknown'
}

// The codes the account forms (sign-up, verification, reset, change of password) answer with.
// Their texts are in errors.json, under account.<code>.
const ACCOUNT_ERROR_CODES = [
  'invalid_email',
  'weak_password',
  'email_already_used',
  'invalid_credentials',
  'invalid_token',
  'no_password_set',
  'account_disabled',
  'too_many_attempts',
] as const

type AccountErrorCode = (typeof ACCOUNT_ERROR_CODES)[number]
type AccountNameErrorCode =
  | 'first_name_required'
  | 'first_name_too_long'
  | 'last_name_required'
  | 'last_name_too_long'
export type AccountErrorKey = `account.${AccountErrorCode | AccountNameErrorCode | 'unknown'}`

/** The field an error belongs to. Without one, the form shows it above its button. */
export type AccountErrorField = 'email' | 'password' | 'currentPassword' | 'firstName' | 'lastName'

const FIELD_OF: Partial<Record<AccountErrorCode, AccountErrorField>> = {
  invalid_email: 'email',
  email_already_used: 'email',
  weak_password: 'password',
  // Only the change of password sends it: the current password is wrong.
  invalid_credentials: 'currentPassword',
}

const KNOWN_ACCOUNT = new Set<string>(ACCOUNT_ERROR_CODES)

/** The message key of a failed account request, and the field to show it next to. */
export function accountError(code: string | undefined): { key: AccountErrorKey; field?: AccountErrorField } {
  const known = code === 'too_many_requests' ? 'too_many_attempts' : code
  if (!known || !KNOWN_ACCOUNT.has(known)) return { key: 'account.unknown' }
  const accountCode = known as AccountErrorCode
  return { key: `account.${accountCode}`, field: FIELD_OF[accountCode] }
}

/** 422 invalid_input on first_name / last_name: one message per field, from the API detail. */
export function invalidInputFieldErrors(
  detail: string,
): Partial<Record<AccountErrorField, AccountErrorKey>> {
  const errors: Partial<Record<AccountErrorField, AccountErrorKey>> = {}
  const first = nameIssue(detail, 'first_name')
  if (first === 'too_long') errors.firstName = 'account.first_name_too_long'
  else if (first) errors.firstName = 'account.first_name_required'
  const last = nameIssue(detail, 'last_name')
  if (last === 'too_long') errors.lastName = 'account.last_name_too_long'
  else if (last) errors.lastName = 'account.last_name_required'
  return errors
}

function nameIssue(detail: string, loc: string): 'required' | 'too_long' | undefined {
  const part = detail.split('; ').find((item) => item.startsWith(`${loc}:`))
  if (!part) return undefined
  return part.includes('at most 100') ? 'too_long' : 'required'
}
