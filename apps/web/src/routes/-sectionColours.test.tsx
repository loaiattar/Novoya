import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse, PreferenceSectionOut, WishResponse } from '../api/generated/types.gen'
import { type CachedWish, wishQueryKey } from '../api/wishes'
import { PreferencesTab } from '../components/organisms/PreferencesTab'
import { createAppRouter } from '../router'

// #165: a section has the same colour on the preference panel and on the Preferences tab, even
// when the two pages show different sections around it.

const CAMILLE: MeResponse = {
  id: '6f1c2b1e-0000-4000-8000-000000000002',
  email: 'camille@exemple.fr',
  name: 'Camille Martin',
  first_name: 'Camille',
  last_name: 'Martin',
  role: 'client',
  locale: 'en',
  status: 'active',
  email_verified: true,
  created_at: '2026-10-01T10:00:00Z',
  sign_in_methods: ['password'],
}

const WISH_ID = '0b5f8a52-0000-4000-8000-000000000010'
const section = (id: string, title: string) => ({
  id,
  title,
  multi: true,
  tags: [{ id: `${id}-tag`, label: `${title} tag`, preselected: false }],
})
const PANEL_WISH: CachedWish = {
  id: WISH_ID,
  status: 'panel_shown',
  destination: { country: 'Greece', city: 'Chania' },
  suggestions: [],
  panel: {
    ask_budget: true,
    ask_persons: true,
    ask_dates: true,
    sections: [section('style', 'Style'), section('rhythm', 'Rhythm'), section('transport', 'Transport'), section('family', 'Family')],
  },
  text: 'A week in Chania',
} satisfies WishResponse & { text: string }

// The tab gathers every wish: other sections than this panel's, in another order.
// family is no catalog section (a back-office offer can use any section:tag).
const PREFERENCES: PreferenceSectionOut[] = ['season', 'food', 'family', 'accommodation', 'transport'].map((id) => ({
  id,
  title: id[0].toUpperCase() + id.slice(1),
  tags: [{ id: `${id}-tag`, label: `${id} tag`, removable: true }],
}))

beforeEach(() => {
  client.setConfig({ baseUrl: 'http://api.test' })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    if (path === '/me') return Response.json(CAMILLE)
    if (path === '/me/preferences') return Response.json(PREFERENCES)
    return Response.json({ status: 'ok' })
  })
})

afterEach(() => vi.restoreAllMocks())

async function panelTone(name: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData<CachedWish>(wishQueryKey(WISH_ID), PANEL_WISH)
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [`/wish/${WISH_ID}/preferences`] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  const tone = (await screen.findByRole('group', { name })).getAttribute('data-tone')
  cleanup()
  return tone
}

async function tabTone(name: string) {
  const rootRoute = createRootRoute()
  const index = createRoute({ getParentRoute: () => rootRoute, path: '/', component: PreferencesTab })
  const router = createRouter({ routeTree: rootRoute.addChildren([index]), history: createMemoryHistory({ initialEntries: ['/'] }) })
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  const tone = (await screen.findByRole('region', { name })).getAttribute('data-tone')
  cleanup()
  return tone
}

describe('section colours across pages', () => {
  it.each(['Transport', 'Family'])('gives %s the same colour on the panel and on the tab', async (name) => {
    const onPanel = await panelTone(name)
    const onTab = await tabTone(name)

    expect(onPanel).toBeTruthy()
    expect(onPanel).toBe(onTab)
  })
})

describe('sections outside the catalog', () => {
  it('all take tone 8, which no catalog section uses', async () => {
    const tones: Record<string, string | null> = {}
    for (const name of ['Season', 'Food', 'Family', 'Accommodation', 'Transport']) tones[name] = await tabTone(name)

    expect(tones.Season).toBe('8')
    expect(tones.Family).toBe('8')
    for (const name of ['Food', 'Accommodation', 'Transport']) expect(tones[name]).not.toBe('8')
  })
})
