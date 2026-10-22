import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { AdminPlan, AdminPlanEntry, AdminQuote, AdminWish, MeResponse } from '../api/generated/types.gen'
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

const ALICE = { id: '00000000-0000-4000-8000-000000000011', name: 'Alice Martin', email: 'alice@example.test' }
const PAUL = { id: '00000000-0000-4000-8000-000000000012', name: 'Paul Agent', email: 'paul@example.test' }
const PLAN_ID = '00000000-0000-4000-8000-000000000301'
const WISH_ID = '00000000-0000-4000-8000-000000000201'
const QUOTE_ID = '00000000-0000-4000-8000-000000000401'

const WISHES: AdminWish[] = [
  {
    id: WISH_ID,
    status: 'planned',
    text: 'A calm week by the sea in Crete',
    country: 'Greece',
    city: 'Chania',
    persons: 2,
    start_date: '2027-05-10',
    end_date: '2027-05-17',
    created_at: '2026-10-20T09:00:00Z',
    updated_at: '2026-10-21T09:00:00Z',
    client: ALICE,
  },
  {
    id: '00000000-0000-4000-8000-000000000202',
    status: 'not_covered',
    text: 'Temples in Kyoto',
    country: 'Japan',
    city: 'Kyoto',
    persons: null,
    start_date: null,
    end_date: null,
    created_at: '2026-10-20T08:00:00Z',
    updated_at: '2026-10-20T08:00:00Z',
    client: null,
  },
]

const PLANS: AdminPlanEntry[] = [
  {
    id: PLAN_ID,
    wish_id: WISH_ID,
    status: 'requested',
    summary: 'Sea and old town',
    created_at: '2026-10-21T09:00:00Z',
    updated_at: '2026-10-21T10:00:00Z',
    country: 'Greece',
    city: 'Chania',
    persons: 2,
    start_date: '2027-05-10',
    end_date: '2027-05-17',
    client: ALICE,
    agent: PAUL,
  },
]

const QUOTES: AdminQuote[] = [
  {
    id: QUOTE_ID,
    number: 'NV-20261022-3FA2C1',
    plan_id: PLAN_ID,
    status: 'expired',
    total: '1860.00',
    currency: 'EUR',
    locale: 'en',
    sent_at: '2026-10-12T09:00:00Z',
    valid_until: '2026-10-19T09:00:00Z',
    country: 'Greece',
    city: 'Chania',
    start_date: '2027-05-10',
    end_date: '2027-05-17',
    client: ALICE,
  },
]

const PLAN: AdminPlan = {
  client: ALICE,
  agent: PAUL,
  plan: {
    id: PLAN_ID,
    wish_id: WISH_ID,
    status: 'negotiating',
    summary: 'Sea and old town',
    assigned_agent_id: PAUL.id,
    items: [
      {
        id: '00000000-0000-4000-8000-000000000501',
        offer_id: '00000000-0000-4000-8000-000000000601',
        day: 3,
        quantity: 2,
        note: null,
        kind: 'activity',
        title: 'Boat trip',
        description: null,
        available: true,
        negotiated_price: null,
        removed: true,
        partner_name: 'Blue Boats',
        partner_contact_email: 'ahoy@blue.example',
        partner_contact_phone: null,
      },
      {
        id: '00000000-0000-4000-8000-000000000502',
        offer_id: '00000000-0000-4000-8000-000000000602',
        day: 1,
        quantity: 6,
        note: null,
        kind: 'hotel',
        title: 'Sea view room',
        description: null,
        available: true,
        negotiated_price: '900.00',
        removed: false,
        partner_name: 'Chania hotel',
        partner_contact_email: 'stay@chania.example',
        partner_contact_phone: null,
      },
    ],
    extras: [
      {
        extra_id: '00000000-0000-4000-8000-000000000701',
        pricing: 'included',
        price_eur: null,
        label: 'Breakfast',
        unit: '',
        needs_quantity_check: false,
        confirmed: true,
      },
    ],
    total: '900.00',
    ready_to_quote: true,
    budget_max: '800.00',
    currency: 'EUR',
    over_budget: true,
    wish_text: 'A calm week by the sea in Crete',
    country: 'Greece',
    city: 'Chania',
    persons: 2,
    start_date: '2027-05-10',
    end_date: '2027-05-17',
  },
}

let me: MeResponse
let wishesAnswer: () => Response
let requests: { path: string; params: URLSearchParams }[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    requests.push({ path: url.pathname, params: url.searchParams })
    if (url.pathname === '/me') return Response.json(me)
    if (url.pathname === '/admin/wishes') return wishesAnswer()
    if (url.pathname === '/admin/plans') return Response.json(PLANS)
    if (url.pathname === `/admin/plans/${PLAN_ID}`) return Response.json(PLAN)
    if (url.pathname === '/admin/quotes') {
      const planId = url.searchParams.get('plan_id')
      return Response.json(planId && planId !== PLAN_ID ? [] : QUOTES)
    }
    return Response.json({ code: 'not_found', detail: 'no route' }, { status: 404 })
  })
}

const sent = (path: string) => requests.filter((request) => request.path === path)

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

describe('admin activity', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    me = ADMIN
    wishesAnswer = () => Response.json(WISHES)
    requests = []
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it("lists every client's wishes with their client and status", async () => {
    renderAt('/admin/activity')

    // The first render of the admin chunk can be slow on a cold start.
    const table = await screen.findByRole('table', { name: "Every client's wishes" }, { timeout: 3000 })
    expect(screen.getByRole('heading', { level: 1, name: 'Activity' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Activity' })).toHaveAttribute('aria-current', 'page')
    const crete = within(table).getByRole('rowheader', { name: /Crete/ }).closest('tr') as HTMLElement
    expect(within(crete).getByText('Alice Martin')).toBeInTheDocument()
    expect(within(crete).getByText('alice@example.test')).toBeInTheDocument()
    expect(within(crete).getByText('Planned')).toBeInTheDocument()
    const kyoto = within(table).getByRole('rowheader', { name: /Kyoto/ }).closest('tr') as HTMLElement
    expect(within(kyoto).getByText('Deleted account')).toBeInTheDocument()
    expect(within(kyoto).getByText('Not covered')).toBeInTheDocument()
  })

  it('sends the search and the status to the API', async () => {
    renderAt('/admin/activity')
    await screen.findByRole('table', { name: "Every client's wishes" }, { timeout: 3000 })

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search by client or destination' }), {
      target: { value: ' crete ' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by status' }), { target: { value: 'planned' } })

    await waitFor(() => {
      const last = sent('/admin/wishes').at(-1)!.params
      expect(last.get('q')).toBe('crete')
      expect(last.get('status')).toBe('planned')
    })
  })

  it("leads from a planned wish to that wish's plans", async () => {
    const { router } = renderAt('/admin/activity')
    await screen.findByRole('table', { name: "Every client's wishes" }, { timeout: 3000 })

    fireEvent.click(screen.getByRole('link', { name: 'See its plans' }))

    await waitFor(() => expect(router.state.location.search).toEqual({ tab: 'plans', wish: WISH_ID }))
    await screen.findByRole('table', { name: "Every client's plans" })
    expect(sent('/admin/plans').at(-1)!.params.get('wish_id')).toBe(WISH_ID)
    expect(screen.getByText('Plans of one wish only.')).toBeInTheDocument()
  })

  it('lists the plans with their agent, the waiting one highlighted', async () => {
    renderAt('/admin/activity?tab=plans')

    const table = await screen.findByRole('table', { name: "Every client's plans" }, { timeout: 3000 })
    const row = within(table).getByRole('rowheader', { name: /Chania, Greece/ }).closest('tr') as HTMLElement
    expect(within(row).getByText('Paul Agent')).toBeInTheDocument()
    expect(within(row).getByText('Quote asked')).toHaveClass('bg-coral')
    expect(within(row).getByRole('link', { name: 'Open the plan to Chania, Greece' })).toHaveAttribute(
      'href',
      `/admin/activity/plans/${PLAN_ID}`,
    )
  })

  it('lists the quotes with their total and status', async () => {
    renderAt('/admin/activity?tab=quotes')

    const table = await screen.findByRole('table', { name: "Every client's quotes" }, { timeout: 3000 })
    const row = within(table).getByRole('rowheader', { name: /NV-20261022-3FA2C1/ }).closest('tr') as HTMLElement
    expect(within(row).getByText('€1,860')).toBeInTheDocument()
    expect(within(row).getByText('Expired')).toBeInTheDocument()
    expect(within(row).getByRole('link', { name: 'NV-20261022-3FA2C1' })).toHaveAttribute(
      'href',
      `/admin/activity/plans/${PLAN_ID}`,
    )
  })

  it('shows a plan read-only with its prices, partners and quote', async () => {
    renderAt(`/admin/activity/plans/${PLAN_ID}`)

    expect(await screen.findByRole('heading', { level: 1, name: 'Chania, Greece' }, { timeout: 3000 })).toBeInTheDocument()
    const table = screen.getByRole('table', { name: "The plan's items, partners and prices" })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(within(rows[0]).getByText('Sea view room')).toBeInTheDocument()
    expect(within(rows[0]).getByText('Chania hotel')).toBeInTheDocument()
    expect(within(rows[0]).getByText('€900')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Removed')).toBeInTheDocument()
    expect(screen.getByText("Over the client's budget")).toBeInTheDocument()
    expect(screen.getByText('Breakfast')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /price/i })).not.toBeInTheDocument()

    const quote = await screen.findByText('NV-20261022-3FA2C1')
    expect(quote).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Download the PDF' })).toHaveAttribute(
      'href',
      `http://api.test/quotes/${QUOTE_ID}/pdf`,
    )
    expect(sent('/admin/quotes').at(-1)!.params.get('plan_id')).toBe(PLAN_ID)
  })

  it("says so when the plan doesn't exist", async () => {
    renderAt('/admin/activity/plans/00000000-0000-4000-8000-000000000399')

    expect(await screen.findByText("This plan doesn't exist.", undefined, { timeout: 3000 })).toBeInTheDocument()
  })

  it('lets the admin try again when a list could not be loaded', async () => {
    wishesAnswer = () => Response.json({ code: 'boom', detail: 'down' }, { status: 500 })
    renderAt('/admin/activity')

    await screen.findByText('This list could not be loaded.', undefined, { timeout: 3000 })
    wishesAnswer = () => Response.json(WISHES)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('table', { name: "Every client's wishes" })).toBeInTheDocument()
  })

  it.each([
    ['client', '/admin/activity'],
    ['agent', '/admin/activity'],
    ['agent', `/admin/activity/plans/${PLAN_ID}`],
  ] as const)('sends someone with the %s role away from %s', async (role, url) => {
    me = { ...ADMIN, role }
    const { router } = renderAt(url)

    await waitFor(() => expect(router.state.location.pathname).toBe('/wish'))
    expect(requests.filter((request) => request.path.startsWith('/admin'))).toHaveLength(0)
  })

  it("shows the activity in the admin's language", async () => {
    me = { ...ADMIN, locale: 'fr' }
    renderAt('/admin/activity?tab=quotes')

    const table = await screen.findByRole('table', { name: 'Les devis de tous les clients' }, { timeout: 3000 })
    expect(screen.getByRole('heading', { level: 1, name: 'Activité' })).toBeInTheDocument()
    expect(within(table).getByText('Expiré')).toBeInTheDocument()
    expect(within(table).getByText(/1\s860\s€/)).toBeInTheDocument()
  })
})
