import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { AdminExtraResponse, MeResponse } from '../api/generated/types.gen'
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

const GUIDE: AdminExtraResponse = {
  id: '00000000-0000-4000-8000-000000000801',
  category: 'Accompagnement',
  label: 'Private guide',
  description: 'A guide for the whole day.',
  pricing: 'supplement',
  supplement_eur: 120,
  unit: 'par jour',
  constraints: [],
  active: true,
  hidden: false,
}

const BREAKFAST: AdminExtraResponse = {
  ...GUIDE,
  id: '00000000-0000-4000-8000-000000000802',
  category: 'Repas',
  label: 'Breakfast',
  pricing: 'included',
  supplement_eur: null,
  unit: '',
}

// Gone from the DÉTOUR export and hidden by an agent: the admin list still shows it.
const TRANSFER: AdminExtraResponse = {
  ...GUIDE,
  id: '00000000-0000-4000-8000-000000000803',
  category: 'Transport',
  label: 'Airport transfer',
  pricing: 'on_quote',
  supplement_eur: null,
  active: false,
  hidden: true,
}

let me: MeResponse
let extras: AdminExtraResponse[]
let listAnswer: () => Response
let patchAnswer: ((body: unknown) => Response) | undefined
let requests: { method: string; path: string; body?: unknown }[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    const body = request.method === 'GET' ? undefined : await request.clone().json().catch(() => undefined)
    requests.push({ method: request.method, path: url.pathname, body })
    if (url.pathname === '/me') return Response.json(me)
    if (url.pathname === '/admin/extras' && request.method === 'GET') return listAnswer()
    const extra = url.pathname.match(/^\/admin\/extras\/([^/]+)$/)
    if (extra && request.method === 'PATCH') {
      if (patchAnswer) return patchAnswer(body)
      extras = extras.map((row) => (row.id === extra[1] ? { ...row, ...(body as object) } : row))
      return Response.json(extras.find((row) => row.id === extra[1]))
    }
    return Response.json({ code: 'not_found', detail: 'no route' }, { status: 404 })
  })
}

const sent = (method: string) => requests.filter((request) => request.method === method && request.path.startsWith('/admin/extras'))

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

const rowOf = (table: HTMLElement, label: string) =>
  within(table).getByRole('rowheader', { name: new RegExp(label) }).closest('tr') as HTMLElement

describe('admin extras', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    me = ADMIN
    extras = [GUIDE, BREAKFAST, TRANSFER]
    listAnswer = () => Response.json(extras)
    patchAnswer = undefined
    requests = []
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('lists every extra with its category, pricing and status', async () => {
    renderAt('/admin/extras')

    // The first render of the admin chunk can be slow on a cold start.
    const table = await screen.findByRole('table', { name: 'Extras and their pricing' }, { timeout: 3000 })
    expect(screen.getByRole('heading', { level: 1, name: 'Extras' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Extras' })).toHaveAttribute('aria-current', 'page')
    const guide = rowOf(table, 'Private guide')
    expect(within(guide).getByText('Accompagnement', { exact: false })).toBeInTheDocument()
    expect(within(guide).getAllByText('€120 par jour').length).toBeGreaterThan(0)
    expect(within(guide).getByRole('checkbox', { name: 'Hidden: Private guide' })).not.toBeChecked()
    expect(within(rowOf(table, 'Breakfast')).getAllByText('Included').length).toBeGreaterThan(0)
    const transfer = rowOf(table, 'Airport transfer')
    expect(within(transfer).getAllByText('On quote').length).toBeGreaterThan(0)
    expect(within(transfer).getAllByText('Inactive', { exact: false }).length).toBeGreaterThan(0)
    expect(within(transfer).getByRole('checkbox', { name: 'Hidden: Airport transfer' })).toBeChecked()
  })

  it('hides an extra, sending only hidden', async () => {
    renderAt('/admin/extras')
    const table = await screen.findByRole('table', { name: 'Extras and their pricing' }, { timeout: 3000 })

    fireEvent.click(within(rowOf(table, 'Private guide')).getByRole('checkbox', { name: 'Hidden: Private guide' }))

    await waitFor(() =>
      expect(sent('PATCH')).toEqual([{ method: 'PATCH', path: `/admin/extras/${GUIDE.id}`, body: { hidden: true } }]),
    )
    await waitFor(() =>
      expect(within(rowOf(table, 'Private guide')).getByRole('checkbox', { name: 'Hidden: Private guide' })).toBeChecked(),
    )
  })

  it('shows a hidden extra again', async () => {
    renderAt('/admin/extras')
    const table = await screen.findByRole('table', { name: 'Extras and their pricing' }, { timeout: 3000 })

    fireEvent.click(within(rowOf(table, 'Airport transfer')).getByRole('checkbox', { name: 'Hidden: Airport transfer' }))

    await waitFor(() => expect(sent('PATCH').map((request) => request.body)).toEqual([{ hidden: false }]))
  })

  it('says so and keeps the switch when the change fails', async () => {
    patchAnswer = () => Response.json({ code: 'boom', detail: 'down' }, { status: 500 })
    renderAt('/admin/extras')
    const table = await screen.findByRole('table', { name: 'Extras and their pricing' }, { timeout: 3000 })

    fireEvent.click(within(rowOf(table, 'Private guide')).getByRole('checkbox', { name: 'Hidden: Private guide' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('The change could not be saved. Please try again.')
    expect(within(rowOf(table, 'Private guide')).getByRole('checkbox', { name: 'Hidden: Private guide' })).not.toBeChecked()
  })

  it('lets the admin try again when the extras could not be loaded', async () => {
    listAnswer = () => Response.json({ code: 'boom', detail: 'down' }, { status: 500 })
    renderAt('/admin/extras')

    await screen.findByText('The extras could not be loaded.', undefined, { timeout: 3000 })
    listAnswer = () => Response.json(extras)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('table', { name: 'Extras and their pricing' })).toBeInTheDocument()
  })

  it('says where the extras come from when there is none', async () => {
    extras = []
    renderAt('/admin/extras')

    expect(await screen.findByText(/No extra yet/, undefined, { timeout: 3000 })).toBeInTheDocument()
  })

  it.each(['client', 'agent'] as const)('sends someone with the %s role away', async (role) => {
    me = { ...ADMIN, role }
    const { router } = renderAt('/admin/extras')

    await waitFor(() => expect(router.state.location.pathname).toBe('/wish'))
    expect(sent('GET')).toHaveLength(0)
  })

  it("shows the extras in the admin's language", async () => {
    me = { ...ADMIN, locale: 'fr' }
    renderAt('/admin/extras')

    const table = await screen.findByRole('table', { name: 'Les extras et leur tarif' }, { timeout: 3000 })
    expect(within(rowOf(table, 'Private guide')).getAllByText(/120\s€ par jour/).length).toBeGreaterThan(0)
    expect(within(rowOf(table, 'Airport transfer')).getAllByText('Sur devis').length).toBeGreaterThan(0)
    expect(within(rowOf(table, 'Airport transfer')).getByRole('checkbox', { name: 'Masqué : Airport transfer' })).toBeChecked()
  })
})
