# 0010. Sign-in with email and password, next to Google

- **Status:** Accepted
- **Date:** 2026-10-18
- **Issue / PR:** auth plan §10.3–10.6 and §12, built in #64 (#63)

## Context

The first architecture only had Google sign-in, so a person without a Google account could
not use Novoya. The team asked for a sign-up form. A password brings more to protect: the
hash, verification and reset emails, and guessing attacks.

## Decision

People can sign up with an email and a password, as `client`s, next to Google:

- The password is hashed with Argon2id (time cost 3, 64 MiB), in a thread. The policy
  follows NIST SP 800-63B: 12 to 128 characters, no common password, no email inside it,
  no composition rules.
- The account must verify its email before signing in (`NOVOYA_REQUIRE_VERIFIED_EMAIL`).
  The link holds a one-time token (24 hours, stored hashed) and points to the web app, which
  calls `POST /auth/email/verify`; a link scanner cannot verify by opening it.
- A forgotten password is reset by email (token valid 30 minutes). A reset signs out every
  session; a password change signs out the others.
- Emails go out over SMTP (Mailpit locally), in English or French.

Against guessing and probing:

- **Rate limits:** at most 50 sign-ins per IP and 10 per email and IP every 15 minutes,
  10 sign-ups per IP per hour, and 3 verification or reset emails per address per hour.
  These are time windows, not account locks, so nobody can lock an owner out on purpose.
- **Same answers:** a wrong email and a wrong password give the same `401`, after the same
  hashing work. `password/forgot` and `email/verify/resend` always answer `202`.
- **One accepted leak:** signing up with an email that already has an account answers
  `409 email_already_used`. This tells that the address is a customer, which we accept for a
  clearer message; the sign-up rate limit stops mass checks.

## Consequences

- One more piece of personal data, the password hash. The privacy page (#45) must list it,
  with the sessions and how long they are kept.
- The web app needs sign-up, verification and reset pages (#62).
- Behind a proxy, the rate limits need the real client IP: uvicorn `--proxy-headers` with the
  proxy's address in `--forwarded-allow-ips`, never `X-Forwarded-For` trusted as is (#48).
- Linking with Google follows [0008](0008-account-linking.md).
