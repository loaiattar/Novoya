# 0016. Advisor chat: messages tied to the wish, read by its client and all staff, polled

- **Status:** Proposed
- **Date:** 2026-10-23
- **Issue / PR:** #169

## Context

While composing a trip (wish, preferences, plan), the client wants to ask the agency
questions. #98 kept chat out of the first scope. The conversation is new personal data, and at
that stage no agent has taken the plan yet, so the usual rule "agents see client data only for
the plans in their queue" (ARCHITECTURE §9) does not give anyone to answer.

## Decision

- A new `messaging` module owns a `messages` table. A conversation is the messages of one
  wish: `wish_id` with `ON DELETE CASCADE`, so `DELETE /me` erases it with the wishes and the
  module needs no step in the account erasure.
- `GET` and `POST /wishes/{id}/messages`. The client who sent the wish reads and writes; so do
  every agent, admin and super admin. Anyone else gets 404, as for a quote, so the id stays
  hidden. A staff line is shown to the client as "the agency", not by agent name.
- The pages poll every 5 seconds while the chat is shown and the tab is visible. No WebSocket
  or server-sent events for a first version: one more read per open window is cheap at the
  agency's size, and it works behind the `/api` proxy without changes (ADR 0011).
- `Cache-Control: private, no-store` on the list.

## Alternatives considered

- **Only the assigned agent reads:** nobody could answer before the plan is requested and
  taken, which is exactly when the client composes.
- **WebSocket / SSE:** live, but a new transport, proxy settings and connection handling for
  a stretch story.

## Consequences

- §9 has one exception: every staff member can read the conversation of any wish.
- The privacy page must list chat messages (follow-up).
- When the queue is busier, a `since` parameter or SSE can replace the full re-read without
  changing the table.
