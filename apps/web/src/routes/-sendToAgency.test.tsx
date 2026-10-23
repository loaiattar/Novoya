import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse, Plan } from '../api/generated/types.gen'
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

const PLAN: Plan = {
  id: PLAN_ID,
  wish_id: '00000000-0000-4000-8000-000000000010',
  status: 'proposed',
  based_on_preferences: true,
  summary: 'Une semaine calme entre mer et vieille ville.',
  items: [
    {
      id: 'i1',
      offer_id: 'o1',
      day: 1,
      quantity: 2,
      note: null,
      kind: 'hotel',
      title: 'Maison face au port',
      description: null,
      available: true,
    },
  ],
  answer_within_days: 5,
}

let plan: Plan
let sendAnswer: () => Response
let sends: number
let signedIn: boolean

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    if (path === '/me') {
      return signedIn ? Response.json(CAMILLE) : Response.json({ code: 'unauthenticated', detail: 'no session' }, { status: 401 })
    }
    if (path === `/plans/${PLAN_ID}` && request.method === 'GET') return Response.json(plan)
    if (path === `/plans/${PLAN_ID}/request-quote` && request.method === 'POST') {
      sends += 1
      return sendAnswer()
    }
    return Response.json([])
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
  return router
}

describe('sending the plan to the agency', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    plan = PLAN
    sends = 0
    signedIn = true
    sendAnswer = () => {
      plan = { ...PLAN, status: 'requested' }
      return Response.json(plan)
    }
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['en-US'])
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('asks to confirm, sends once, then says when the agency answers', async () => {
    renderAt(`/plans/${PLAN_ID}`)

    fireEvent.click(await screen.findByRole('button', { name: 'Send to the agency' }))
    const dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText(/answer within 5 days/)).toBeInTheDocument()
    expect(sends).toBe(0)
    fireEvent.click(within(dialog).getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('Sent to the agency. An advisor will answer within 5 days.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send to the agency' })).not.toBeInTheDocument()
    expect(sends).toBe(1)
  })

  it('sends nothing when the client cancels', async () => {
    renderAt(`/plans/${PLAN_ID}`)

    fireEvent.click(await screen.findByRole('button', { name: 'Send to the agency' }))
    fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
    expect(sends).toBe(0)
  })

  it('shows the plan as sent when it was sent already (a second tab, a second click)', async () => {
    sendAnswer = () => {
      plan = { ...PLAN, status: 'requested' }
      return Response.json({ code: 'invalid_transition', detail: 'the plan is not proposed' }, { status: 409 })
    }
    renderAt(`/plans/${PLAN_ID}`)

    fireEvent.click(await screen.findByRole('button', { name: 'Send to the agency' }))
    fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('Sent to the agency. An advisor will answer within 5 days.')).toBeInTheDocument()
    expect(sends).toBe(1)
  })

  it('says an advisor works on it once the plan is taken', async () => {
    plan = { ...PLAN, status: 'negotiating' }
    renderAt(`/plans/${PLAN_ID}`)

    expect(await screen.findByText('An advisor is working on it.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send to the agency' })).not.toBeInTheDocument()
  })

  it.each([
    ['quoted', 'Quote ready'],
    ['accepted', 'Accepted'],
    ['rejected', 'Declined'],
  ] as const)('says the plan is %s as My trips does, not that an advisor works on it', async (status, label) => {
    plan = { ...PLAN, status }
    renderAt(`/plans/${PLAN_ID}`)

    expect(await screen.findByRole('status')).toHaveTextContent(label)
    expect(screen.queryByText('An advisor is working on it.')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Follow it on My trips' })).toHaveAttribute('href', '/trips')
    expect(screen.queryByRole('button', { name: 'Send to the agency' })).not.toBeInTheDocument()
  })

  it('lets the client try again when sending failed', async () => {
    sendAnswer = () => Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
    renderAt(`/plans/${PLAN_ID}`)

    fireEvent.click(await screen.findByRole('button', { name: 'Send to the agency' }))
    fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Send' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Your trip could not be sent. Try again.')
    expect(screen.getByRole('button', { name: 'Send to the agency' })).toBeEnabled()
  })

  it('sends the client to sign in again when the session ended, then back to the plan', async () => {
    sendAnswer = () => {
      signedIn = false
      return Response.json({ code: 'unauthenticated', detail: 'no session' }, { status: 401 })
    }
    const router = renderAt(`/plans/${PLAN_ID}`)

    fireEvent.click(await screen.findByRole('button', { name: 'Send to the agency' }))
    fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: `/plans/${PLAN_ID}` })
    expect(screen.queryByText('Your trip could not be sent. Try again.')).not.toBeInTheDocument()
  })
})
