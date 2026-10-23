# 0016. Advisor chat: messages tied to the wish, read by its client, the admins and the plan's agent, polled

- **Status:** Proposed
- **Date:** 2026-10-23
- **Issue / PR:** #169

## Context

While composing a trip (wish, preferences, plan), the client wants to ask the agency
questions. #98 kept chat out of the first scope. The conversation is new personal data, and at
that stage no agent may have taken the plan yet. The rule of ARCHITECTURE §9, "agents see
client data only for the plans in their queue", must still hold.

## Decision

- A new `messaging` module owns a `messages` table. A conversation is the messages of one
  wish: `wish_id` with `ON DELETE CASCADE`, so `DELETE /me` erases it with the wishes and the
  module needs no step in the account erasure.
- `GET` and `POST /wishes/{id}/messages`, with one rule for both
  (`messaging.domain.message.may_read`):
  - the client who sent the wish, and the admins and super admins, always;
  - an agent while a plan of the wish waits in the queue (requested, nobody took it), or when
    they are its assigned agent: the plans `GET /agent/plans` and `GET /agent/plans/{id}` show
    them. Once another agent takes the plan, the others lose the chat too;
  - a wish with no plan, or only a proposed one: the client and the admins only.
  Anyone else gets 404, as for a quote, so the id stays hidden. Messaging reads the plans'
  status and agent through `planning.public.plans_of_wish`, behind its own `Plans` port. A staff
  line is shown to the client as "the agency", not by agent name.
- Each author posts at most 30 messages in 5 minutes (the shared `RateLimiter`, 429
  `too_many_requests` with `Retry-After`).
- The pages poll every 5 seconds while the chat is shown and the tab is visible. No WebSocket
  or server-sent events for a first version: one more read per open window is cheap at the
  agency's size, and it works behind the `/api` proxy without changes (ADR 0011).
- `Cache-Control: private, no-store` on the list and on a posted message.

## Alternatives considered

- **Every staff member reads every chat:** simple, and anyone can answer at once, but an agent
  would keep reading a client's chat after another agent took the plan, which breaks §9.
- **Only the assigned agent reads:** nobody could answer while the plan waits in the queue.
- **WebSocket / SSE:** live, but a new transport, proxy settings and connection handling for
  a stretch story.

## Consequences

- Before the client asks for a quote (no plan, or a proposed one), only the admins can answer. The agents see the chat once the plan is in the queue.
- The privacy page must list chat messages (follow-up).
- When the queue is busier, a `since` parameter or SSE can replace the full re-read without
  changing the table.
