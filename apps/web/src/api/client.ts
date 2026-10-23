import { toApiError } from './errors'
import { client } from './generated/client.gen'

// The API is served under /api on the web app's own origin, through a proxy (Vite in
// development, the host's rewrites in production), so the session cookie is first-party.
// Set VITE_API_URL to override.
client.setConfig({
  baseUrl: import.meta.env.VITE_API_URL ?? '/api',
  credentials: 'include',
})

// Without this, a failed request throws only the parsed body, without its HTTP status.
client.interceptors.error.use(toApiError)
