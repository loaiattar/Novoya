import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { listFeaturedOffersQueryKey } from '../api/generated/@tanstack/react-query.gen'
import { client } from '../api/generated/client.gen'
import type { FeaturedOfferResponse } from '../api/generated/types.gen'
import { createAppRouter } from '../router'

// What GET /offers/featured answers: the offers an agent featured, by title.
const FEATURED: FeaturedOfferResponse[] = [
  {
    id: '00000000-0000-4000-8000-000000000061',
    kind: 'hotel',
    title: 'Riad room in the medina',
    description: 'A house around a hidden courtyard.',
    country: 'Morocco',
    city: 'Marrakech',
  },
  {
    id: '00000000-0000-4000-8000-000000000062',
    kind: 'activity',
    title: 'Surf lesson on Grande Plage',
    description: 'Half a day facing the Atlantic.',
    country: 'France',
    city: 'Biarritz',
  },
]

let featuredAnswer: () => Response

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    if (path === '/me') return Response.json({ code: 'unauthenticated', detail: 'no session' }, { status: 401 })
    if (path === '/offers/featured') return featuredAnswer()
    if (path === '/reviews') return Response.json([])
    return Response.json({ status: 'ok' })
  })
}

function renderAt(url: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [url] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, queryClient }
}

// The featured offers answered (a list or an error), so the page shows its final state.
async function featuredSettled(queryClient: QueryClient) {
  await waitFor(() => expect(queryClient.getQueryState(listFeaturedOffersQueryKey())?.status).not.toBe('pending'))
}

describe('home page inspirations', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    featuredAnswer = () => Response.json(FEATURED)
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('shows one card per featured offer, each opening that offer', async () => {
    renderAt('/')

    const section = await screen.findByRole('region', { name: 'A few ideas to branch off.' })
    const links = within(section)
      .getAllByRole('link')
      .filter((link) => link.getAttribute('href')?.startsWith('/offers/'))
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/offers/00000000-0000-4000-8000-000000000061',
      '/offers/00000000-0000-4000-8000-000000000062',
    ])
    expect(within(section).getByText('Riad room in the medina')).toBeInTheDocument()
    expect(within(section).getByText('Morocco · Marrakech')).toBeInTheDocument()
    expect(within(section).getByText('Half a day facing the Atlantic.')).toBeInTheDocument()
    expect(within(section).queryByRole('link', { name: /wish/i })).not.toBeInTheDocument()
  })

  it('names the countries in French for a French visitor', async () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['fr-FR'])
    renderAt('/')

    const section = await screen.findByRole('region', { name: 'Quelques idées pour bifurquer.' })
    expect(within(section).getByText('Maroc · Marrakech')).toBeInTheDocument()
  })

  it('asks a visitor to sign in, then comes back to that offer', async () => {
    const { router } = renderAt('/')

    fireEvent.click(await screen.findByText('Surf lesson on Grande Plage'))

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: '/offers/00000000-0000-4000-8000-000000000062' })
  })

  it('has no inspirations section when no offer is featured', async () => {
    featuredAnswer = () => Response.json([])
    const { queryClient } = renderAt('/')

    await featuredSettled(queryClient)
    expect(screen.queryByRole('region', { name: 'A few ideas to branch off.' })).not.toBeInTheDocument()
  })

  it('has no inspirations section when the offers could not be loaded', async () => {
    featuredAnswer = () => Response.json({ code: 'internal', detail: 'down' }, { status: 500 })
    const { queryClient } = renderAt('/')

    await featuredSettled(queryClient)
    expect(screen.queryByRole('region', { name: 'A few ideas to branch off.' })).not.toBeInTheDocument()
  })
})
