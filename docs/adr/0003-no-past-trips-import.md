# 0003. No import of the client's past trips

- **Status:** Accepted
- **Date:** 2026-10-16
- **Issue / PR:** #55 (Architecture 0.3)

## Context

An early idea was to read the client's Gmail, Google Docs or Instagram to find their past
trips and suggest similar ones. The school refused it: reading a mailbox, documents or
social media to profile a client is not GDPR compliant for this project.

## Decision

Novoya only stores what the client types into it: the wish, the panel answers, the budget,
the travellers and the dates. It never reads a mailbox, documents or social media.

Google sign-in asks only for `openid email profile`. Novoya keeps no Google token and no
avatar.

## Consequences

- The preference panel, built from the tags of partner offers, replaces the profile we would
  have guessed from past trips.
- No Gmail, Drive or Instagram scope, so Google needs no app verification for the consent
  screen (#14).
- The privacy page (#45) can list exactly what is stored, and `DELETE /me` (#46) can remove
  all of it.
- Any future feature that reads outside data needs a new ADR and a GDPR review first.
