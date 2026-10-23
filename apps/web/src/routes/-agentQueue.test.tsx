import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { AgentPlan, MeResponse, QueueEntry } from '../api/generated/types.gen'
import { formatDayRange } from '../lib/format'
import { createAppRouter } from '../router'

const AGENT: MeResponse = {
  id: '00000000-0000-4000-8000-000000000003',
  email: 'sami@detour.example',
  name: 'Sami Haddad',
  first_name: 'Sami',
  last_name: 'Haddad',
  role: 'agent',
  locale: 'en',
  status: 'active',
  email_verified: true,
  created_at: '2026-08-18T10:00:00Z',
  sign_in_methods: ['password'],
}

const CHANIA: QueueEntry = {
  custom: false,
  id: '00000000-0000-4000-8000-000000000020',
  wish_id: '00000000-0000-4000-8000-000000000010',
  status: 'requested',
  summary: 'Une semaine calme entre mer et vieille ville.',
  updated_at: '2026-10-22T08:00:00Z',
  wish_text: 'De bonnes tables et beaucoup de mer.',
  country: 'Greece',
  city: 'Chania',
  persons: 2,
  start_date: '2027-05-12',
  end_date: '2027-05-19',
  budget_max: '3500.00',
  currency: 'EUR',
}

// No budget given by the client.
const BIARRITZ: QueueEntry = {
  ...CHANIA,
  id: '00000000-0000-4000-8000-000000000021',
  wish_id: '00000000-0000-4000-8000-000000000011',
  summary: 'Du surf le matin, l’océan le soir.',
  wish_text: 'Surfer et bien manger.',
  country: 'France',
  city: 'Biarritz',
  persons: 1,
  budget_max: null,
}

const FES: QueueEntry = {
  ...CHANIA,
  id: '00000000-0000-4000-8000-000000000022',
  wish_id: '00000000-0000-4000-8000-000000000012',
  status: 'negotiating',
  summary: 'Fès, derrière les portes.',
  wish_text: 'Un riad au calme.',
  country: 'Morocco',
  city: 'Fès',
}

const SETE: QueueEntry = {
  ...CHANIA,
  id: '00000000-0000-4000-8000-000000000023',
  wish_id: '00000000-0000-4000-8000-000000000013',
  status: 'quoted',
  summary: 'Sète, entre étang et mer.',
  wish_text: 'Des huîtres et du calme.',
  country: 'France',
  city: 'Sète',
}

const TAKEN: AgentPlan = {
  custom: false,
  outline: null,
  id: CHANIA.id,
  wish_id: CHANIA.wish_id,
  status: 'negotiating',
  summary: CHANIA.summary,
  items: [],
  extras: [],
  total: '0.00',
  ready_to_quote: false,
  budget_max: CHANIA.budget_max,
  currency: 'EUR',
  over_budget: false,
  assigned_agent_id: AGENT.id,
  wish_text: CHANIA.wish_text,
  country: CHANIA.country,
  city: CHANIA.city,
  persons: CHANIA.persons,
  start_date: CHANIA.start_date,
  end_date: CHANIA.end_date,
}

let me: MeResponse
let queue: QueueEntry[]
let takeAnswer: () => Response
let requests: { method: string; path: string; search: string; body?: unknown }[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    const body = request.method === 'GET' ? undefined : await request.clone().json().catch(() => undefined)
    requests.push({ method: request.method, path: url.pathname, search: url.search, body })
    if (url.pathname === '/me') return Response.json(me)
    if (url.pathname === '/agent/plans' && request.method === 'GET') {
      const statuses = url.searchParams.getAll('status')
      return Response.json(queue.filter((entry) => statuses.includes(entry.status)))
    }
    if (url.pathname === `/agent/plans/${CHANIA.id}/take` && request.method === 'POST') return takeAnswer()
    if (url.pathname === `/agent/plans/${CHANIA.id}` && request.method === 'GET') return Response.json(TAKEN)
    return Response.json({ code: 'not_found', detail: 'no route' }, { status: 404 })
  })
}

const queueReads = () => requests.filter((request) => request.method === 'GET' && request.path === '/agent/plans')
const statusesOf = (search: string) => new URLSearchParams(search).getAll('status')
const rowOf = (summary: string) => screen.getByRole('heading', { name: summary }).closest('article') as HTMLElement
// Radix tabs switch on mouse down, as a pointer does.
const openTab = async (name: RegExp) => fireEvent.mouseDown(await screen.findByRole('tab', { name }))

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

describe('agent quote queue', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    me = AGENT
    queue = [CHANIA, BIARRITZ, FES, SETE]
    takeAnswer = () => Response.json(TAKEN)
    requests = []
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('reads each tab from GET /agent/plans with its statuses', async () => {
    renderAt('/agent')

    expect(await screen.findByRole('tab', { name: 'To take · 2' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'In progress · 1' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Decided · 1' })).toBeInTheDocument()
    const searches = queueReads().map((request) => statusesOf(request.search))
    expect(searches).toContainEqual(['requested'])
    expect(searches).toContainEqual(['negotiating'])
    expect(searches).toContainEqual(['quoted', 'accepted', 'rejected'])
  })

  it('shows the summary, wish, place, dates, travellers and budget of a request', async () => {
    renderAt('/agent')

    await screen.findByRole('heading', { name: CHANIA.summary })
    const row = rowOf(CHANIA.summary)
    expect(within(row).getByText(CHANIA.wish_text, { exact: false })).toBeInTheDocument()
    expect(within(row).getByText('Chania, Greece')).toBeInTheDocument()
    // toHaveTextContent folds the page's spaces, not the expected text's: formatRange puts
    // thin spaces around the dash.
    const dates = formatDayRange('en', '2027-05-12', '2027-05-19').replace(/\s+/g, ' ')
    expect(row).toHaveTextContent(`${dates} · 2 travellers`)
    expect(within(row).getByText('€3,500')).toBeInTheDocument()
  })

  it('says when a client gave no budget', async () => {
    renderAt('/agent')

    await screen.findByRole('heading', { name: BIARRITZ.summary })
    expect(within(rowOf(BIARRITZ.summary)).getByText('No budget given')).toBeInTheDocument()
  })

  it('shows real requests, without the demo banner', async () => {
    renderAt('/agent')

    await screen.findByRole('heading', { name: CHANIA.summary })
    expect(screen.queryByText('Demo data.')).not.toBeInTheDocument()
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })

  it('takes a plan with POST /take and opens it', async () => {
    const { router } = renderAt('/agent')

    await screen.findByRole('heading', { name: CHANIA.summary })
    fireEvent.click(within(rowOf(CHANIA.summary)).getByRole('button', { name: 'Take the plan' }))

    await waitFor(() => expect(router.state.location.pathname).toBe(`/agent/plans/${CHANIA.id}`))
    expect(requests).toContainEqual(expect.objectContaining({ method: 'POST', path: `/agent/plans/${CHANIA.id}/take` }))
  })

  it('says another agent took the plan, and reads the queue again', async () => {
    takeAnswer = () => {
      queue = queue.filter((entry) => entry.id !== CHANIA.id)
      return Response.json({ code: 'invalid_transition', detail: 'already taken' }, { status: 409 })
    }
    const { router } = renderAt('/agent')
    await screen.findByRole('heading', { name: CHANIA.summary })
    const readsBefore = queueReads().filter((request) => statusesOf(request.search).includes('requested')).length

    fireEvent.click(within(rowOf(CHANIA.summary)).getByRole('button', { name: 'Take the plan' }))

    expect(await screen.findByText('Another agent took this plan.')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('heading', { name: CHANIA.summary })).not.toBeInTheDocument())
    const readsAfter = queueReads().filter((request) => statusesOf(request.search).includes('requested')).length
    expect(readsAfter).toBeGreaterThan(readsBefore)
    expect(router.state.location.pathname).toBe('/agent')
  })

  it('takes one plan at a time', async () => {
    let finish!: () => void
    const pending = new Promise<Response>((resolve) => (finish = () => resolve(Response.json(TAKEN))))
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const request = input instanceof Request ? input : new Request(String(input))
      const url = new URL(request.url)
      requests.push({ method: request.method, path: url.pathname, search: url.search })
      if (url.pathname === '/me') return Response.json(me)
      if (url.pathname === '/agent/plans') {
        const statuses = url.searchParams.getAll('status')
        return Response.json(queue.filter((entry) => statuses.includes(entry.status)))
      }
      if (url.pathname.endsWith('/take')) return pending
      return Response.json(TAKEN)
    })
    renderAt('/agent')
    await screen.findByRole('heading', { name: BIARRITZ.summary })

    fireEvent.click(within(rowOf(CHANIA.summary)).getByRole('button', { name: 'Take the plan' }))
    await waitFor(() => expect(within(rowOf(BIARRITZ.summary)).getByRole('button', { name: 'Take the plan' })).toBeDisabled())
    fireEvent.click(within(rowOf(BIARRITZ.summary)).getByRole('button', { name: 'Take the plan' }))
    finish()

    await waitFor(() => expect(requests.filter((request) => request.path.endsWith('/take'))).toHaveLength(1))
  })

  it('links a plan in progress to its page', async () => {
    renderAt('/agent')

    await openTab(/^In progress/)

    expect(await screen.findByRole('link', { name: FES.summary })).toHaveAttribute('href', `/agent/plans/${FES.id}`)
    expect(screen.queryByRole('button', { name: 'Take the plan' })).not.toBeInTheDocument()
  })

  it('lists a decided plan with its status and a link to it', async () => {
    renderAt('/agent')

    await openTab(/^Decided/)

    expect(await screen.findByRole('link', { name: SETE.summary })).toHaveAttribute('href', `/agent/plans/${SETE.id}`)
    expect(within(rowOf(SETE.summary)).getByText('Quoted')).toBeInTheDocument()
  })

  it.each(['/agent', `/agent/plans/${CHANIA.id}`])('sends a client away from %s', async (url) => {
    me = { ...AGENT, role: 'client' }
    const { router } = renderAt(url)

    await waitFor(() => expect(router.state.location.pathname).toBe('/wish'))
  })
})
