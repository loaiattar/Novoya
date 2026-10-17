# `src/api/`

HTTP only. No UI, no business rules.

| Path | What |
|---|---|
| `queryClient.ts` | TanStack Query client (cache, retries) |
| `generated/` | Created by `pnpm gen:api` from `openapi.json`. Do not edit. |

When the backend exists, replace `openapi.json` with the FastAPI spec and run `pnpm gen:api` again.
