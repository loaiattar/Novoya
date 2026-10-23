import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse, Trip } from '../api/generated/types.gen'
import { createAppRouter } from '../router'

const CAMILLE: MeResponse = {
  id: '6f1c2b1e-0000-4000-8000-000000000003',
  email: 'camille@exemple.fr',
  name: 'Camille Durand',
  first_name: 'Camille',
  last_name: 'Durand',
  role: 'client',
  locale: 'en',
  status: 'active',
  email_verified: true,
  created_at: '2026-10-01T10:00:00Z',
  sign_in_methods: ['password'],
}

const PLAN_ID = '00000000-0000-4000-8000-000000000020'
const QUOTE_ID = '00000000-0000-4000-8000-000000000030'
const PANEL_WISH_ID = '00000000-0000-4000-8000-000000000011'

function trip(overrides: Partial<Trip>): Trip {
  return {
    wish_id: '00000000-0000-4000-8000-000000000010',
    text: 'Une semaine calme',
    status: 'answered',
    country: 'Grèce',
    city: 'Chania',
    persons: 2,
    start_date: '2026-12-01',
    end_date: '2026-12-08',
    created_at: '2026-10-20T10:00:00Z',
    plan_id: null,
    plan_status: null,
    quote_id: null,
    answer_within_days: 4,
    ...overrides,
  }
}

let trips: Trip[]
let failing: boolean
let router: ReturnType<typeof createAppRouter> | undefined

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    if (path === '/me') return Response.json(CAMILLE)
    if (path === '/me/trips') {
      return failing ? Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 }) : Response.json(trips)
    }
    return Response.json([])
  })
}

function renderAt(url: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [url] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('the trips page', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    trips = []
    failing = false
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['en-US'])
    mockApi()
  })
  afterEach(async () => {
    await waitFor(() => expect(router?.state.status).toBe('idle'))
    vi.restoreAllMocks()
  })

  it('says there are no trips and links to the wish page', async () => {
    renderAt('/trips')

    expect(await screen.findByText(/No trips yet/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Describe a trip' })).toHaveAttribute('href', '/wish')
  })

  it('opens the page each trip is at', async () => {
    trips = [
      trip({ text: 'Voyage devis', status: 'planned', plan_id: PLAN_ID, plan_status: 'quoted', quote_id: QUOTE_ID }),
      trip({ text: 'Voyage plan', status: 'planned', plan_id: PLAN_ID, plan_status: 'proposed' }),
      trip({ text: 'Voyage panneau', status: 'panel_shown', wish_id: PANEL_WISH_ID }),
    ]
    renderAt('/trips')

    expect(await screen.findByRole('link', { name: /Voyage devis/ })).toHaveAttribute('href', `/quotes/${QUOTE_ID}`)
    expect(screen.getByRole('link', { name: /Voyage plan/ })).toHaveAttribute('href', `/plans/${PLAN_ID}`)
    expect(screen.getByRole('link', { name: /Voyage panneau/ })).toHaveAttribute(
      'href',
      `/wish/${PANEL_WISH_ID}/preferences`,
    )
  })

  it('shows where each trip stands, without a demo banner', async () => {
    trips = [trip({ text: 'Voyage devis', status: 'planned', plan_id: PLAN_ID, plan_status: 'quoted', quote_id: QUOTE_ID })]
    renderAt('/trips')

    expect(await screen.findByText('Quote ready')).toBeInTheDocument()
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })

  it('says a sent trip is with the agency and when the answer comes, then that an advisor works on it', async () => {
    trips = [
      trip({ text: 'Voyage envoyé', status: 'planned', plan_id: PLAN_ID, plan_status: 'requested', answer_within_days: 6 }),
      trip({ text: 'Voyage en cours', status: 'planned', plan_id: PLAN_ID, plan_status: 'negotiating', wish_id: PANEL_WISH_ID }),
    ]
    renderAt('/trips')

    expect(await screen.findByText('Sent to the agency')).toBeInTheDocument()
    expect(screen.getByText('Answer within 6 days')).toBeInTheDocument()
    expect(screen.getByText('An advisor is working on it')).toBeInTheDocument()
  })

  it('says when the trips could not be loaded', async () => {
    failing = true
    renderAt('/trips')

    expect(await screen.findByText('Your trips could not be loaded.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
