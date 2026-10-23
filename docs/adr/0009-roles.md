# 0009. Three roles stored on the user: client, agent, admin

- **Status:** Replaced by [0015](0015-super-admin-role.md)
- **Date:** 2026-10-18
- **Issue / PR:** auth plan §4.3 and §15, built in #49 (#63)

## Context

Clients use the assistant, agency staff (agents) price the plans and send quotes, and someone
must decide who is staff. The first proposal gave the `agent` role to the emails listed in
`NOVOYA_AGENT_EMAILS`, which needs a redeploy for every change and rewrites the role at each
sign-in.

## Decision

`users.role` is one of `client`, `agent` or `admin`, and it is the only source of truth. The
roles are fixed and never get rights case by case, so there is no permission table.

- A new account is always a `client`. Signing in never changes a role.
- Only an admin changes a role (`PATCH /admin/users/{id}/role`), never their own, and only
  to `agent` or `admin` for a verified email. There is always at least one admin.
- The first admin is named with a server command: `grant-role --email ... --role admin`.
- Every change is logged in `role_changes`: before, after, by whom, how, when.
- Routes are protected on the router with `require_client`, `require_agent` or
  `require_admin` from `accounts.public`. The admin passes all three.

## Options considered

- **`client` and `agent`, with `NOVOYA_AGENT_EMAILS`:** no admin pages, but a redeploy for
  each change, and no way to remove an agent without one.
- **A permissions model (per role or per user):** more flexible, but nothing here needs it
  with three fixed roles and one role per user.

## Consequences

- The role is read from the database on every request ([0007](0007-server-side-sessions.md)),
  so a demotion applies at the next request, on every session.
- The web app uses the `role` from `GET /me` to show or hide menus. That is only display:
  the server checks the role on every route.
- Two admins demoting each other at once still keep one admin: the count locks the rows
  (`FOR UPDATE`).
