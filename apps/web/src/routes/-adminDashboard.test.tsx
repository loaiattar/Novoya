import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { AdminStatsResponse, MeResponse } from '../api/generated/types.gen'
import { createAppRouter } from '../router'

const ADMIN: MeResponse = {
  id: '00000000-0000-4000-8000-000000000001',
  email: 'nadia@example.test',
  name: 'Nadia Ferhat',
  first_name: 'Nadia',
  last_name: 'Ferhat',
  role: 'admin',
  locale: 'en',
  status: 'active',
  email_verified: true,
  created_at: '2026-08-18T10:00:00Z',
  sign_in_methods: ['password'],
}

const STATS: AdminStatsResponse = {
  partners: { active: 8, hidden: 1, inactive: 2 },
  offers: { active: 40, hidden: 3, inactive: 0 },
  extras: { active: 10, hidden: 2, inactive: 0 },
  reviews: { published: 6, hidden: 1 },
  users: { client: 12, agent: 2, admin: 1, super_admin: 1 },
  plans: { proposed: 5, requested: 3, negotiating: 1, quoted: 2, accepted: 1, rejected: 0 },
  quotes: { open: 2, expired: 1, accepted: 1, rejected: 4 },
}

let me: MeResponse
let statsAnswer: () => Response
let requests: string[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    requests.push(url.pathname)
    if (url.pathname === '/me') return Response.json(me)
    if (url.pathname === '/admin/stats') return statsAnswer()
    return Response.json([])
  })
}

function renderAt(url: string) {
  // The app's 30 seconds of freshness (router.tsx), so that a stale count would show.
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } })
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [url] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router }
}

const tile = (name: RegExp) => screen.getByRole('link', { name })

describe('admin dashboard', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    me = ADMIN
    statsAnswer = () => Response.json(STATS)
    requests = []
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('opens /admin on the key numbers, read in one request', async () => {
    renderAt('/admin')

    // The first render of the admin chunk can be slow on a cold start.
    expect(await screen.findByRole('heading', { level: 1, name: 'Overview' }, { timeout: 3000 })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: /Plans waiting for a quote/ })).toHaveTextContent('3')
    expect(requests.filter((path) => path.startsWith('/admin'))).toEqual(['/admin/stats'])
    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
  })

  it('links each number to its page', async () => {
    renderAt('/admin')
    await screen.findByRole('link', { name: /Plans waiting for a quote/ }, { timeout: 3000 })

    expect(tile(/Plans waiting for a quote/)).toHaveAttribute('href', '/admin/activity?tab=plans')
    expect(tile(/Quotes waiting for the client/)).toHaveAttribute('href', '/admin/activity?tab=quotes')
    expect(tile(/Expired quotes/)).toHaveAttribute('href', '/admin/activity?tab=quotes')
    expect(tile(/Active partners/)).toHaveAttribute('href', '/admin/partners')
    expect(tile(/Active offers/)).toHaveAttribute('href', '/admin/partners')
    expect(tile(/Active extras/)).toHaveAttribute('href', '/admin/extras')
    expect(tile(/Published reviews/)).toHaveAttribute('href', '/admin/reviews')
    expect(tile(/^16\s*Accounts/)).toHaveAttribute('href', '/admin/users')
  })

  it('says what each number leaves out', async () => {
    renderAt('/admin')
    const partners = await screen.findByRole('link', { name: /Active partners/ }, { timeout: 3000 })

    expect(partners).toHaveTextContent('8')
    expect(within(partners).getByText('1 hidden')).toBeInTheDocument()
    expect(within(partners).getByText(/^2 no longer in /)).toBeInTheDocument()
    // Nothing left DÉTOUR: no line for it.
    expect(within(tile(/Active offers/)).queryByText(/no longer in/)).not.toBeInTheDocument()
    expect(within(tile(/Accepted quotes/)).getByText('4 rejected')).toBeInTheDocument()
    expect(within(tile(/Accounts/)).getByText('12 clients · 2 agents · 2 admins')).toBeInTheDocument()
  })

  it('opens the users page from the nav', async () => {
    const { router } = renderAt('/admin')
    fireEvent.click(await screen.findByRole('link', { name: 'Users' }, { timeout: 3000 }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/admin/users'))
  })

  it('reads the numbers again when the admin comes back', async () => {
    const { router } = renderAt('/admin')
    await screen.findByRole('link', { name: /Active partners/ }, { timeout: 3000 })
    await router.navigate({ to: '/admin/users' })
    statsAnswer = () => Response.json({ ...STATS, partners: { active: 7, hidden: 2, inactive: 2 } })

    await router.navigate({ to: '/admin' })

    await waitFor(() => expect(tile(/Active partners/)).toHaveTextContent(/^7/))
    expect(requests.filter((path) => path === '/admin/stats')).toHaveLength(2)
  })

  it('offers a retry when the numbers cannot be loaded', async () => {
    statsAnswer = () => Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
    renderAt('/admin')

    expect(await screen.findByText('The numbers could not be loaded.', {}, { timeout: 3000 })).toBeInTheDocument()
    statsAnswer = () => Response.json(STATS)
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))

    expect(await screen.findByRole('link', { name: /Plans waiting for a quote/ })).toBeInTheDocument()
  })

  it("shows the numbers in the admin's language", async () => {
    me = { ...ADMIN, locale: 'fr' }
    renderAt('/admin')

    expect(await screen.findByRole('heading', { level: 1, name: "Vue d'ensemble" }, { timeout: 3000 })).toBeInTheDocument()
    const partners = await screen.findByRole('link', { name: /Partenaires actifs/ })
    expect(within(partners).getByText('1 masqué')).toBeInTheDocument()
    expect(within(tile(/Offres actives/)).getByText('3 masquées')).toBeInTheDocument()
    expect(within(partners).getByText(/^2 retirés de /)).toBeInTheDocument()
    expect(within(tile(/Devis acceptés/)).getByText('4 refusés')).toBeInTheDocument()
  })
})
