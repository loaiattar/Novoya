# Architecture decision records

One short file per decision that shapes Novoya: the context, what we decided, and what it
changes. To add one, copy [0000-template.md](0000-template.md) to the next number and add it
below. An accepted ADR is never rewritten to change the decision: a new ADR replaces it.

| # | Decision | Status |
|---|---|---|
| [0001](0001-use-fastapi.md) | Use FastAPI for the backend | Accepted |
| [0002](0002-modular-monolith.md) | One repository, and a modular monolith with Clean Architecture | Accepted |
| [0003](0003-no-past-trips-import.md) | No import of the client's past trips (GDPR) | Accepted |
| [0004](0004-in-process-travel-tools.md) | Travel tools as in-process functions, not an MCP server | Accepted |
| [0005](0005-openrouter-llm.md) | OpenRouter as the LLM provider | Accepted |
| [0006](0006-negotiated-prices-pdf-quote.md) | No fixed prices: a human agent negotiates and sends a PDF quote | Accepted, partly replaced by 0014 |
| [0007](0007-server-side-sessions.md) | Opaque server-side sessions, not JWT | Accepted |
| [0008](0008-account-linking.md) | One account per email, linked across Google and password | Accepted |
| [0009](0009-roles.md) | Three roles stored on the user: client, agent, admin | Replaced by 0015 |
| [0010](0010-email-password-sign-in.md) | Sign-in with email and password, next to Google | Accepted |
| [0011](0011-same-origin-api-proxy.md) | The browser reaches the API under /api on the web app's origin | Accepted |
| [0012](0012-i18n-i18next.md) | i18next for the web app's translations, one file per language and screen | Proposed |
| [0013](0013-host-the-demo-on-render.md) | Host the demo on Render: static web app, Docker API, managed PostgreSQL | Proposed |
| [0014](0014-indicative-prices-and-detour-import.md) | Indicative partner prices on the offer page, and the DÉTOUR catalog import | Accepted |
| [0015](0015-super-admin-role.md) | Four roles: a super admin acts on admins, and super admins are managed on the server | Accepted |
| [0016](0016-advisor-chat.md) | Advisor chat: messages tied to the wish, read by its client and all staff, polled | Proposed |
