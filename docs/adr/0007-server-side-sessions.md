# 0007. Opaque server-side sessions, not JWT

- **Status:** Accepted
- **Date:** 2026-10-16
- **Issue / PR:** auth plan §11.1, built in #63

## Context

After sign-in, every request must say who is calling and with which role. Signing out,
resetting a password, deleting an account or changing a role must take effect at once. The
backend is one service with one database ([0002](0002-modular-monolith.md)).

## Decision

A session is an opaque random token (256 bits) in an HttpOnly cookie, `SameSite=Lax`. Only
its SHA-256 is stored, in `sessions`. On each request the server reads the session and the
user, role included, in one indexed query.

- A session ends after 7 days without use, and after 30 days at most.
- `last_seen_at` is written at most every 5 minutes.
- Each sign-in gets a new token and revokes the one the browser already had (no fixation).
- In production the cookie is `Secure` and named `__Host-novoya_session`.

## Options considered

- **A JWT with the role, and a refresh token:** no database read per request, but a demoted
  agent keeps their rights until the token expires, unless we keep a deny list. The refresh
  token would have to be in the database anyway, and we would add key rotation and token
  renewal in the web app.

## Consequences

- One indexed read per authenticated request.
- Revocation is immediate, on every device: `POST /auth/logout-all`, a password reset and a
  role change all apply at the next request.
- The choice sits behind `SessionOpener`, `SessionRepository` and `AuthenticateSession`:
  moving to JWT would only change these three.
- The web app and the API must stay on the same site (for example `app.` and `api.` of one
  domain), or the cookie becomes third-party and is blocked. This constrains the hosting
  choice (#48).
