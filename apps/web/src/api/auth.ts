import { client } from './generated/client.gen'

/**
 * Where the browser goes to sign in with Google. It is a full page navigation, not a fetch:
 * the API answers with redirects and sets a state cookie on the way.
 */
export function googleSignInUrl(redirectTo: string): string {
  const baseUrl = (client.getConfig().baseUrl ?? '').replace(/\/$/, '')
  return `${baseUrl}/auth/google/login?${new URLSearchParams({ redirect_to: redirectTo })}`
}
