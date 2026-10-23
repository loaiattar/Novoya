# 0011. The browser reaches the API under /api on the web app's origin

- **Status:** Accepted
- **Date:** 2026-10-19
- **Issue / PR:** #16, #81

## Context

The session is an HttpOnly cookie with `SameSite=Lax` ([0007](0007-server-side-sessions.md)).
A browser sends it on a `fetch` only when the web app and the API are on the same site. If
they end up on two different domains (for example `novoya.vercel.app` and
`novoya-api.onrender.com`), the cookie becomes third-party: `/me` always answers 401 and
every user is sent back to `/login`, even right after signing in. The hosting is not chosen
yet (#48), and we do not want it to decide whether sign-in works.

## Decision

The browser only talks to the web app's origin. The API is served under `/api` on that
origin by a proxy that strips the prefix and forwards to the API, wherever it is hosted.

- Locally, Vite's dev server is the proxy (`apps/web/vite.config.ts`, `API_PROXY_TARGET`).
  In production, it is the host's rewrite rule (`/api/*` to the API), or nginx.
- The generated client calls `/api` (`VITE_API_URL`). The API code does not change.
- Google comes back through the proxy: `NOVOYA_API_PUBLIC_URL` is the web app's origin +
  `/api`, and `<that>/auth/google/callback` is the redirect URI registered at Google.
- The proxy sends `X-Forwarded-For`, and uvicorn trusts it only from the proxy
  (`FORWARDED_ALLOW_IPS`), so the rate limits count each browser, not the proxy.

## Options considered

- **`SameSite=None; Secure` with CORS:** the cookie is still third-party. Safari and Firefox
  already block third-party cookies by default, and Chrome restricts them, so part of the
  users could not sign in.
- **A token in an `Authorization` header, kept by the web app:** JavaScript would see the
  token, so an XSS could steal it. This goes back on the HttpOnly session of 0007.
- **Require the same domain at hosting time** (`app.` and `api.` of one domain): works, but
  forces a custom domain and both services under it, and fails silently if anyone forgets.

## Consequences

- The cookie is first-party wherever the API runs. CORS is no longer needed by the web
  app; `NOVOYA_CORS_ORIGINS` stays for the Origin check of unsafe requests.
- The hosting of the web app must support a rewrite or a proxy to the API. This replaces the
  "same site" constraint at the end of 0007.
- Each environment needs its own redirect URI at Google (locally
  `http://localhost:5173/api/auth/google/callback`).
- In production, `FORWARDED_ALLOW_IPS` must be the proxy's address, never `*`: otherwise a
  client could set its own `X-Forwarded-For` and dodge the rate limits.
- The API stays reachable directly on its own port (docs at `:8000/docs`), but the web app
  never calls it there.
