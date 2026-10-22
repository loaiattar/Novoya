import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { AdminReviewResponse, MeResponse } from '../api/generated/types.gen'
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

// Made-up reviews for the admin table. Authors follow the published form.
const NORA: AdminReviewResponse = {
  id: '00000000-0000-4000-8000-000000000051',
  country: 'Greece',
  city: 'Chania',
  rating: 5,
  reviewed_on: '2026-08-21',
  text: 'A made-up stay by the sea.',
  author: 'Nora N.',
  hidden: false,
}

const ANONYME: AdminReviewResponse = {
  id: '00000000-0000-4000-8000-000000000052',
  country: 'France',
  city: 'Lille',
  rating: 4,
  reviewed_on: '2026-07-13',
  text: 'Another made-up review.',
  author: 'Voyageur anonyme',
  hidden: true,
}

type Answer = (body: unknown) => Response | Promise<Response>

let me: MeResponse
let reviews: AdminReviewResponse[]
let reviewsAnswer: () => Response | Promise<Response>
let saveAnswer: Answer | undefined
let requests: { method: string; path: string; body?: unknown }[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    const body = request.method === 'GET' ? undefined : await request.clone().json().catch(() => undefined)
    requests.push({ method: request.method, path: url.pathname, body })
    if (url.pathname === '/me') return Response.json(me)
    if (request.method !== 'GET' && saveAnswer) return saveAnswer(body)
    if (url.pathname === '/admin/reviews' && request.method === 'GET') return reviewsAnswer()
    const patch = url.pathname.match(/^\/admin\/reviews\/([^/]+)$/)
    if (patch && request.method === 'PATCH') {
      reviews = reviews.map((row) => (row.id === patch[1] ? { ...row, ...(body as object) } : row))
      return Response.json(reviews.find((row) => row.id === patch[1]))
    }
    return Response.json({ code: 'not_found', detail: 'no route' }, { status: 404 })
  })
}

const sent = (method: string, path: string) =>
  requests.filter((request) => request.method === method && request.path === path)

function renderAt(url: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [url] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router }
}

describe('admin reviews', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    me = ADMIN
    reviews = [NORA, ANONYME]
    reviewsAnswer = () => Response.json(reviews)
    saveAnswer = undefined
    requests = []
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('lists every published review, including a hidden one', async () => {
    renderAt('/admin/reviews')

    const table = await screen.findByRole('table', { name: 'Published reviews' }, { timeout: 3000 })
    expect(screen.getByRole('heading', { level: 1, name: 'Reviews' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Reviews' })).toHaveAttribute('aria-current', 'page')
    expect(within(table).getByRole('rowheader', { name: /Nora N\./ })).toBeInTheDocument()
    expect(within(table).getByText('Chania, Greece')).toBeInTheDocument()
    expect(within(table).getAllByText('A made-up stay by the sea.').length).toBeGreaterThan(0)
    const hidden = within(table).getByRole('checkbox', { name: 'Hidden: Voyageur anonyme' })
    expect(hidden).toBeChecked()
    expect(within(table).getByRole('checkbox', { name: 'Hidden: Nora N.' })).not.toBeChecked()
    expect(sent('GET', '/admin/reviews')).toHaveLength(1)
  })

  it('hides a review, sending only hidden', async () => {
    renderAt('/admin/reviews')

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Hidden: Nora N.' }, { timeout: 3000 }))

    await waitFor(() =>
      expect(sent('PATCH', `/admin/reviews/${NORA.id}`).map((request) => request.body)).toEqual([{ hidden: true }]),
    )
    // The saved row replaces the old one: the whole list is not loaded again.
    await waitFor(() => expect(screen.getByRole('checkbox', { name: 'Hidden: Nora N.' })).toBeChecked())
    expect(sent('GET', '/admin/reviews')).toHaveLength(1)
  })

  it('still says a switch failed when another one succeeds meanwhile', async () => {
    saveAnswer = (body) =>
      (body as { hidden?: boolean }).hidden === true
        ? Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
        : Response.json({ ...ANONYME, hidden: false })
    renderAt('/admin/reviews')

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Hidden: Nora N.' }, { timeout: 3000 }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Hidden: Voyageur anonyme' }))

    await waitFor(() => expect(sent('PATCH', `/admin/reviews/${ANONYME.id}`)).toHaveLength(1))
    expect(await screen.findByRole('alert')).toHaveTextContent('The change could not be saved. Please try again.')
  })

  it.each([
    ['client', '/admin/reviews'],
    ['agent', '/admin/reviews'],
  ] as const)('sends someone with the %s role away from the reviews page', async (role, url) => {
    me = { ...ADMIN, role }
    const { router } = renderAt(url)

    await waitFor(() => expect(router.state.location.pathname).toBe('/wish'))
    expect(sent('GET', '/admin/reviews')).toHaveLength(0)
  })

  it("shows the reviews in the admin's language", async () => {
    me = { ...ADMIN, locale: 'fr' }
    renderAt('/admin/reviews')

    expect(await screen.findByRole('heading', { level: 1, name: 'Avis' }, { timeout: 3000 })).toBeInTheDocument()
    expect(await screen.findByRole('table', { name: 'Avis publiés' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Avis' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('checkbox', { name: 'Masqué : Nora N.' })).toBeInTheDocument()
    expect(document.documentElement).toHaveAttribute('lang', 'fr')
  })
})
