# Novoya web

React + TypeScript + Vite, with TanStack Router (file-based routes), TanStack Query and TanStack Form. See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).

## Run locally

Needs Node 22 and pnpm. The API should run on http://localhost:8000.

```bash
cp .env.example .env
pnpm install
pnpm dev
```

The app runs on http://localhost:5173.

## Folders

```
src/
  main.tsx, router.tsx   app entry and router setup
  routes/                pages (TanStack file-based routing)
    __root.tsx, index.tsx
    wishes/              send a wish, the preference panel
    plans/               the proposed plan, "Ask for a quote"
    quotes/              the quote, PDF download, accept or reject
    agent/               agent pages: quote queue, pricing
    admin/               partners and offers
    settings/            account, delete my data
  components/            shared components
    ui/                  buttons, inputs, layout pieces
    panel/               PanelSection, TagPicker
    plan/  quote/  agent/
  api/                   API client setup; generated/ is created by pnpm gen
  hooks/                 shared React hooks
  lib/                   small helpers (dates, money formatting)
  i18n/                  English and French texts
  test/                  test setup
```

A page lives in `routes/`; anything used by two pages moves to `components/`.

## Generated code

Both are created by `pnpm gen`, which `dev`, `build`, `typecheck` and `test` run first. They are not committed.

- `src/api/generated/`: the typed API client and TanStack Query helpers, from `../api/openapi.json`.
- `src/routeTree.gen.ts`: the route tree, from the files in `src/routes/`.

To call an endpoint, use the generated query options:

```tsx
import { useQuery } from '@tanstack/react-query'
import { getHealthOptions } from '../api/generated/@tanstack/react-query.gen'

const { data } = useQuery(getHealthOptions())
```

## Checks

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```
