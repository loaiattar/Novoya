# 0008. One account per email, linked across Google and password

- **Status:** Accepted
- **Date:** 2026-10-18
- **Issue / PR:** auth plan §10.2 and §12.4, built in #15 (#73)

## Context

A person can sign up with an email and a password, and later sign in with Google using the
same address, or the other way round. They expect one account, not two. But linking on the
email alone opens two takeovers:

- **Pre-hijacking:** someone signs up with the victim's address and a password they know,
  without being able to verify it, and waits for the victim to sign in with Google.
- **An address Google does not own:** a Google account can carry a company address, checked
  once by Google. A former employee who made it back then could take over the Novoya account
  on that address.

## Decision

Accounts are separate from their ways of signing in: `password_credentials` holds at most one
password per user, and `oauth_identities` one row per provider account, unique on
`(provider, subject)` and on `(user_id, provider)`.

A Google sign-in resolves the account in this order:

1. The Google account (`sub`) is linked already: sign that user in. The email is not used.
2. An account has the same email: link Google to it, but only when Google owns the address
   (`@gmail.com`, or a Workspace domain in the `hd` claim) and the account has no other
   Google account. If the account was never verified, its password and sessions are dropped
   first. Otherwise the person must sign in with their password.
3. No account: create one, as a verified `client`.

Signing in never changes a role. Google's name only fills an empty name.

## Consequences

- One person, one account, whatever way they sign in. `GET /me` lists both methods.
- A Google sign-in on a non-Gmail address with an existing account ends on
  `/login?error=oauth_link_not_allowed`. Linking Google from inside a signed-in password
  account is a follow-up.
- Races (two tabs, two Google accounts at once) are settled by the unique indexes and one
  retry, covered by Postgres tests.
