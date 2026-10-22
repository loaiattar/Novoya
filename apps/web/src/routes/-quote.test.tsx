import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse, QuoteDetail } from '../api/generated/types.gen'
import { createAppRouter } from '../router'

const CLIENT: MeResponse = {
  id: '00000000-0000-4000-8000-000000000003',
  email: 'nadia@exemple.fr',
  name: 'Nadia Test',
  first_name: 'Nadia',
  last_name: 'Test',
  role: 'client',
  locale: 'en',
  status: 'active',
  email_verified: true,
  created_at: '2026-10-01T10:00:00Z',
  sign_in_methods: ['password'],
}

const QUOTE_ID = '00000000-0000-4000-8000-000000000051'

// What GET /quotes/{id} answers for an open quote.
const OPEN: QuoteDetail = {
  id: QUOTE_ID,
  number: 'NV-20261019-3FA2C1',
  plan_id: '00000000-0000-4000-8000-000000000020',
  total: '1234.50',
  currency: 'EUR',
  locale: 'en',
  sent_at: '2026-10-19T09:00:00Z',
  valid_until: '2026-10-26T09:00:00Z',
  status: 'open',
  decided_at: null,
  client_comment: null,
  agent_name: 'Paul Agent',
  country: 'Greece',
  city: 'Chania',
  start_date: '2027-05-10',
  end_date: '2027-05-17',
  persons: 2,
  budget_max: '1500.00',
  items: [
    { day: 1, kind: 'hotel', title: 'Sea view room', description: null, quantity: 6, price: '900.00' },
    { day: 3, kind: 'activity', title: 'Boat trip', description: null, quantity: 2, price: '289.50' },
  ],
  extras: [
    { label: 'Private guide', unit: 'per activity', price: '45.00' },
    { label: 'Breakfast', unit: '', price: null },
  ],
}

let quote: QuoteDetail
let answerResponse: () => Response
let answers: { path: string; body: unknown }[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    if (path === '/me') return Response.json(CLIENT)
    if (path === `/quotes/${QUOTE_ID}`) return Response.json(quote)
    if (request.method === 'POST' && path.startsWith(`/quotes/${QUOTE_ID}/`)) {
      answers.push({ path, body: await request.json() })
      return answerResponse()
    }
    return Response.json({ code: 'not_found', detail: 'no such quote' }, { status: 404 })
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
}

describe('quote page', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    quote = OPEN
    answers = []
    answerResponse = () => new Response(null, { status: 204 })
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('shows the quote the agent sent, with its lines, total and validity', async () => {
    renderAt(`/quotes/${QUOTE_ID}`)

    expect(await screen.findByRole('heading', { level: 1, name: /Your trip.*to Chania/ })).toBeInTheDocument()
    expect(screen.getByText(/Paul Agent/)).toBeInTheDocument()
    expect(screen.getByText('Sea view room')).toBeInTheDocument()
    expect(screen.getByText('Day 1 · 6 units')).toBeInTheDocument()
    expect(screen.getByText('€289.50')).toBeInTheDocument()
    expect(screen.getByText('Included')).toBeInTheDocument()
    expect(screen.getByText('€1,234.50')).toBeInTheDocument()
    expect(screen.getByText('Valid until October 26, 2026')).toBeInTheDocument()
    expect(screen.getByText('8 days / 7 nights')).toBeInTheDocument()
    expect(screen.getByText(/€1,500/)).toBeInTheDocument()
  })

  it('downloads the PDF from the API', async () => {
    renderAt(`/quotes/${QUOTE_ID}`)

    const link = await screen.findByRole('link', { name: /Download the offer PDF/ })
    expect(link).toHaveAttribute('href', `http://api.test/quotes/${QUOTE_ID}/pdf`)
  })

  it('accepts the quote with the comment, then shows the answer', async () => {
    renderAt(`/quotes/${QUOTE_ID}`)

    fireEvent.change(await screen.findByRole('textbox', { name: /comment/ }), { target: { value: 'Lovely' } })
    quote = { ...OPEN, status: 'accepted', decided_at: '2026-10-20T10:00:00Z', client_comment: 'Lovely' }
    fireEvent.click(screen.getByRole('button', { name: 'Accept the offer' }))

    expect(await screen.findByText('You accepted this offer on October 20, 2026.')).toBeInTheDocument()
    expect(answers).toEqual([{ path: `/quotes/${QUOTE_ID}/accept`, body: { comment: 'Lovely' } }])
    expect(screen.getByRole('button', { name: 'Accept the offer' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Decline the offer' })).toBeDisabled()
    expect(screen.getByText('Lovely')).toBeInTheDocument()
  })

  it('rejects the quote without a comment', async () => {
    renderAt(`/quotes/${QUOTE_ID}`)

    const decline = await screen.findByRole('button', { name: 'Decline the offer' })
    quote = { ...OPEN, status: 'rejected', decided_at: '2026-10-20T10:00:00Z' }
    fireEvent.click(decline)

    expect(await screen.findByText('You declined this offer on October 20, 2026.')).toBeInTheDocument()
    expect(answers).toEqual([{ path: `/quotes/${QUOTE_ID}/reject`, body: { comment: null } }])
  })

  it('disables the buttons of an expired quote and says so', async () => {
    quote = { ...OPEN, status: 'expired' }
    renderAt(`/quotes/${QUOTE_ID}`)

    expect(await screen.findByText('This offer expired on October 26, 2026.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Accept the offer' })).toBeDisabled()
  })

  it('says when an answer did not go through, and lets the client try again', async () => {
    answerResponse = () => Response.json({ code: 'unavailable', detail: 'down' }, { status: 503 })
    renderAt(`/quotes/${QUOTE_ID}`)

    fireEvent.click(await screen.findByRole('button', { name: 'Accept the offer' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("Your answer didn't go through.")
    await waitFor(() => expect(screen.getByRole('button', { name: 'Accept the offer' })).toBeEnabled())
  })

  it('shows the new state when the quote expired meanwhile', async () => {
    answerResponse = () => Response.json({ code: 'quote_expired', detail: 'expired' }, { status: 409 })
    renderAt(`/quotes/${QUOTE_ID}`)

    const accept = await screen.findByRole('button', { name: 'Accept the offer' })
    quote = { ...OPEN, status: 'expired' }
    fireEvent.click(accept)

    expect(await screen.findByText('This offer expired on October 26, 2026.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('says the quote does not exist for another id', async () => {
    renderAt('/quotes/00000000-0000-4000-8000-000000000099')

    expect(await screen.findByText("This offer doesn't exist.")).toBeInTheDocument()
  })
})
