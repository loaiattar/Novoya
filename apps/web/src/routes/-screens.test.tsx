import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse, Plan, UserResponse } from '../api/generated/types.gen'
import { createAppRouter } from '../router'

const ADMIN: MeResponse = {
  id: '00000000-0000-4000-8000-000000000001',
  email: 'arthur@novoya.fr',
  name: 'Arthur Roche',
  first_name: 'Arthur',
  last_name: 'Roche',
  role: 'admin',
  locale: 'en',
  status: 'active',
  email_verified: true,
  created_at: '2026-08-18T10:00:00Z',
  sign_in_methods: ['password'],
}

const LEA: UserResponse = {
  id: '00000000-0000-4000-8000-000000000002',
  email: 'lea@novoya.fr',
  name: 'Léa Morel',
  first_name: 'Léa',
  last_name: 'Morel',
  role: 'client',
  locale: 'fr',
  status: 'active',
  email_verified: true,
  created_at: '2026-09-04T10:00:00Z',
}

const PLAN_ID = '00000000-0000-4000-8000-000000000020'

const PLAN: Plan = {
  id: PLAN_ID,
  wish_id: '00000000-0000-4000-8000-000000000010',
  status: 'proposed',
  based_on_preferences: false,
  summary: 'Une semaine calme entre mer et vieille ville.',
  items: [
    { id: 'i3', offer_id: 'o3', day: 2, quantity: 1, note: null, kind: null, title: null, description: null, available: false },
    {
      id: 'i1',
      offer_id: 'o1',
      day: 1,
      quantity: 2,
      note: 'Arrivée en fin de journée.',
      kind: 'hotel',
      title: 'Maison face au port',
      description: 'Chambres sur la baie.',
      available: true,
    },
    { id: 'i2', offer_id: 'o2', day: 2, quantity: 1, note: null, kind: 'guide', title: 'Chania à pied', description: null, available: true },
  ],
}

let me: MeResponse
let signedIn: boolean
let planAnswer: (path: string) => Response | Promise<Response>
let users: UserResponse[]
let requests: { method: string; path: string; search: string; body?: unknown }[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    const body = request.method === 'GET' ? undefined : await request.clone().json().catch(() => undefined)
    requests.push({ method: request.method, path: url.pathname, search: url.search, body })
    if (url.pathname === '/me') {
      return signedIn ? Response.json(me) : Response.json({ code: 'unauthenticated', detail: 'no session' }, { status: 401 })
    }
    if (url.pathname === '/admin/users') return Response.json(users)
    if (url.pathname.startsWith('/plans/') && request.method === 'GET') return planAnswer(url.pathname)
    const role = url.pathname.match(/^\/admin\/users\/([^/]+)\/role$/)
    if (role && request.method === 'PATCH') {
      const next = (body as { role: UserResponse['role'] }).role
      users = users.map((user) => (user.id === role[1] ? { ...user, role: next } : user))
      return Response.json(users.find((user) => user.id === role[1]))
    }
    return Response.json({ status: 'ok' })
  })
}

const patches = () => requests.filter((request) => request.method === 'PATCH')

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

describe('back-office and plan screens', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    me = ADMIN
    signedIn = true
    users = [ADMIN, LEA]
    planAnswer = (path) =>
      path === `/plans/${PLAN_ID}`
        ? Response.json(PLAN)
        : path === '/plans/foo'
          ? Response.json({ code: 'invalid_input', detail: 'plan_id: not a UUID' }, { status: 422 })
          : Response.json({ code: 'plan_not_found', detail: 'no plan' }, { status: 404 })
    requests = []
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('lists the users for an admin', async () => {
    renderAt('/admin')

    // The first render of the admin chunk can be slow on a cold start.
    const table = await screen.findByRole('table', { name: 'Users and roles' }, { timeout: 3000 })
    expect(within(table).getByRole('rowheader', { name: /Léa Morel/ })).toBeInTheDocument()
    expect(within(table).getByRole('rowheader', { name: /Arthur Roche/ })).toBeInTheDocument()
  })

  it('asks before changing a role, then sends PATCH /admin/users/{id}/role', async () => {
    renderAt('/admin')

    const select = await screen.findByRole('combobox', { name: 'Role of Léa Morel' })
    fireEvent.change(select, { target: { value: 'agent' } })

    const dialog = await screen.findByRole('alertdialog', { name: "Change Léa Morel's role?" })
    expect(dialog).toHaveTextContent('Léa Morel will go from Client to Agent.')
    expect(patches()).toHaveLength(0)
    fireEvent.click(within(dialog).getByRole('button', { name: 'Change role' }))

    await waitFor(() =>
      expect(requests).toContainEqual(
        expect.objectContaining({ method: 'PATCH', path: `/admin/users/${LEA.id}/role`, body: { role: 'agent' } }),
      ),
    )
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Role of Léa Morel' })).toHaveValue('agent'))
  })

  it('sends nothing when the admin cancels the role change', async () => {
    renderAt('/admin')

    const select = await screen.findByRole('combobox', { name: 'Role of Léa Morel' })
    // What the arrow keys do on a closed <select> in Windows: one change per key press.
    fireEvent.change(select, { target: { value: 'admin' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
    expect(patches()).toHaveLength(0)
    expect(screen.getByRole('combobox', { name: 'Role of Léa Morel' })).toHaveValue('client')
  })

  it('does not let an admin change their own role', async () => {
    renderAt('/admin')

    expect(await screen.findByRole('combobox', { name: 'Role of Arthur Roche' })).toBeDisabled()
  })

  it('filters the users by role', async () => {
    renderAt('/admin')

    fireEvent.change(await screen.findByRole('combobox', { name: 'Filter by role' }), { target: { value: 'agent' } })

    await waitFor(() =>
      expect(requests).toContainEqual(expect.objectContaining({ path: '/admin/users', search: expect.stringContaining('role=agent') })),
    )
  })

  it("shows the admin page in the admin's language", async () => {
    me = { ...ADMIN, locale: 'fr' }
    renderAt('/admin')

    expect(await screen.findByRole('heading', { level: 1, name: 'Utilisateurs' })).toBeInTheDocument()
    expect(await screen.findByRole('table', { name: 'Utilisateurs et rôles' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Rôle de Léa Morel' })).toHaveDisplayValue('Client')
    expect(document.documentElement).toHaveAttribute('lang', 'fr')
  })

  it('formats the quote amounts in the interface language', async () => {
    renderAt('/quotes/NV-2026-0182')

    expect(await screen.findByText('€2,750')).toBeInTheDocument()
    expect(screen.getByText('7 days / 6 nights')).toBeInTheDocument()
  })

  it.each(['/agent', '/admin'])('sends a client away from %s', async (url) => {
    me = { ...ADMIN, role: 'client' }
    const { router } = renderAt(url)

    await waitFor(() => expect(router.state.location.pathname).toBe('/wish'))
  })

  it('opens the agency queue for an agent, but not the admin pages', async () => {
    me = { ...ADMIN, role: 'agent' }
    const { router } = renderAt('/agent')

    expect(await screen.findByRole('heading', { name: 'Quote requests' })).toBeInTheDocument()

    await router.navigate({ to: '/admin' })
    await waitFor(() => expect(router.state.location.pathname).toBe('/wish'))
  })

  it('shows a plan without any price', async () => {
    renderAt('/plans/chania')

    expect(await screen.findByRole('heading', { level: 1, name: 'Chania, au rythme de la mer.' })).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('€')
  })

  it('shows a plan from the API, day by day, without any price', async () => {
    renderAt(`/plans/${PLAN_ID}`)

    expect(await screen.findByRole('heading', { level: 1, name: 'Your trip, day by day.' })).toBeInTheDocument()
    expect(screen.getByText(PLAN.summary)).toBeInTheDocument()
    expect(screen.getByText(/You picked no preference/)).toBeInTheDocument()
    expect(screen.getByText('The price will come in a quote from a DÉTOUR advisor.')).toBeInTheDocument()
    const days = screen.getAllByRole('heading', { level: 2, name: /^Day / }).map((heading) => heading.textContent)
    expect(days).toEqual(['Day 1', 'Day 2'])
    expect(screen.getByRole('heading', { name: 'Maison face au port' })).toBeInTheDocument()
    expect(screen.getByText('Stay')).toBeInTheDocument()
    expect(screen.getByText('× 2')).toBeInTheDocument()
    expect(screen.getByText('This offer is no longer available.')).toBeInTheDocument()
    expect(screen.queryByRole('note')).not.toBeInTheDocument() // real data: no demo banner
    expect(document.body.textContent).not.toContain('€')
  })

  it("says so when the plan is missing or not the client's", async () => {
    renderAt('/plans/00000000-0000-4000-8000-000000000099')

    expect(await screen.findByText("This preview doesn't exist.")).toBeInTheDocument()
  })

  it.each([
    ['an id that is no plan id', '/plans/foo'],
    ['a plan the caller may not read', `/plans/${PLAN_ID}`],
  ])('says the plan does not exist for %s, with no retry', async (_, url) => {
    if (url.endsWith(PLAN_ID)) planAnswer = () => Response.json({ code: 'forbidden', detail: 'clients only' }, { status: 403 })
    renderAt(url)

    expect(await screen.findByText("This preview doesn't exist.")).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('lets the client try again when the plan could not be loaded', async () => {
    planAnswer = () => Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
    renderAt(`/plans/${PLAN_ID}`)

    expect(await screen.findByText('Your plan could not be loaded.')).toBeInTheDocument()
    let finish!: (response: Response) => void
    planAnswer = () => new Promise((resolve) => (finish = resolve))
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('Loading your plan…')).toBeInTheDocument()
    finish(Response.json(PLAN))
    expect(await screen.findByText(PLAN.summary)).toBeInTheDocument()
  })

  it('sends to the sign-in page when the session ended, to come back after', async () => {
    planAnswer = () => {
      signedIn = false
      return Response.json({ code: 'unauthenticated', detail: 'no session' }, { status: 401 })
    }
    const { router } = renderAt(`/plans/${PLAN_ID}`)

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: `/plans/${PLAN_ID}` })
  })

  it('does not lead from the plan to a priced quote', async () => {
    renderAt('/plans/chania')

    expect(await screen.findByRole('button', { name: 'Ask an advisor for a quote' })).toBeDisabled()
    expect(screen.getByText('Asking for a quote is coming soon.')).toBeInTheDocument()
    expect(document.querySelector('a[href^="/quotes/"]')).toBeNull()
  })

  it('counts in each agency tab exactly the requests it lists', async () => {
    me = { ...ADMIN, role: 'agent' }
    renderAt('/agent')

    expect(await screen.findByRole('tab', { name: 'To assign · 3' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'In progress · 0' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Decided · 0' })).toBeInTheDocument()
  })

  it('says the demo plan has no price yet', async () => {
    renderAt('/plans/chania')

    expect(await screen.findByText('The price will come in a quote from a DÉTOUR advisor.')).toBeInTheDocument()
  })

  it('shows a day of the plan from the API, without any price', async () => {
    renderAt(`/plans/${PLAN_ID}/days/2`)

    expect(await screen.findByRole('heading', { level: 1, name: 'Day 2' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Chania à pied' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Chania à pied' })).toHaveAttribute('href', expect.stringMatching(/^\/offers\//))
    expect(screen.getByText('Guide')).toBeInTheDocument()
    expect(screen.getByText('This offer is no longer available.')).toBeInTheDocument()
    expect(screen.queryByText('Maison face au port')).not.toBeInTheDocument() // day 1
    expect(screen.getByRole('link', { name: '← Day 1' })).toHaveAttribute('href', `/plans/${PLAN_ID}/days/1`)
    expect(screen.queryByRole('link', { name: /→$/ })).not.toBeInTheDocument() // the last day
    expect(screen.queryByRole('note')).not.toBeInTheDocument() // real data: no demo banner
    expect(document.body.textContent).not.toContain('€')
  })

  it('opens a day from the plan at once, from the cached plan', async () => {
    renderAt(`/plans/${PLAN_ID}`)
    const day = await screen.findByRole('link', { name: 'Day 2' })
    // The plan is read again in the background (stale), but the day never waits for it.
    planAnswer = () => new Promise(() => {})
    fireEvent.click(day)

    expect(await screen.findByRole('heading', { level: 1, name: 'Day 2' })).toBeInTheDocument()
    expect(screen.queryByText('Loading your plan…')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '← Back to the preview' })).toHaveAttribute('href', `/plans/${PLAN_ID}`)
  })

  it('keeps the day on screen when reading the plan again in the background fails', async () => {
    const { queryClient } = renderAt(`/plans/${PLAN_ID}`)
    const day = await screen.findByRole('link', { name: 'Day 2' })
    let fail!: () => void
    planAnswer = () =>
      new Promise((resolve) => (fail = () => resolve(Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 }))))
    fireEvent.click(day)
    expect(await screen.findByRole('heading', { level: 1, name: 'Day 2' })).toBeInTheDocument()

    await waitFor(() => expect(fail).toBeDefined())
    fail()

    await waitFor(() => expect(queryClient.isFetching()).toBe(0))
    expect(screen.queryByText('Your plan could not be loaded.')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Day 2' })).toBeInTheDocument()
  })

  it.each(['0', '3', '9', 'abc'])('says day %s is not a day of the trip', async (day) => {
    renderAt(`/plans/${PLAN_ID}/days/${day}`)

    expect(await screen.findByText("This day doesn't exist.")).toBeInTheDocument()
  })

  it.each([
    ['a plan that does not exist', () => Response.json({ code: 'plan_not_found', detail: 'no plan' }, { status: 404 })],
    ['a plan the caller may not read', () => Response.json({ code: 'forbidden', detail: 'clients only' }, { status: 403 })],
    ['an id that is no plan id', () => Response.json({ code: 'invalid_input', detail: 'plan_id: not a UUID' }, { status: 422 })],
  ])('says the day does not exist for %s, with no retry', async (_, answer) => {
    planAnswer = answer
    renderAt(`/plans/${PLAN_ID}/days/1`)

    expect(await screen.findByText("This preview doesn't exist.")).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('lets the client try again when the day could not be loaded', async () => {
    planAnswer = () => Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
    renderAt(`/plans/${PLAN_ID}/days/1`)

    expect(await screen.findByText('Your plan could not be loaded.')).toBeInTheDocument()
    planAnswer = () => Response.json(PLAN)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { name: 'Maison face au port' })).toBeInTheDocument()
  })

  it('sends to the sign-in page from a day when the session ended, to come back to that day', async () => {
    planAnswer = () => {
      signedIn = false
      return Response.json({ code: 'unauthenticated', detail: 'no session' }, { status: 401 })
    }
    const { router } = renderAt(`/plans/${PLAN_ID}/days/2`)

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: `/plans/${PLAN_ID}/days/2` })
  })

  it("shows a day in the client's language", async () => {
    me = { ...ADMIN, role: 'client', locale: 'fr' }
    renderAt(`/plans/${PLAN_ID}/days/1`)

    expect(await screen.findByRole('heading', { level: 1, name: 'Jour 1' })).toBeInTheDocument()
    expect(screen.getByText('Hébergement')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Jour 2 →' })).toBeInTheDocument()
  })

  it('does not open day pages from the demo plan', async () => {
    renderAt('/plans/chania')

    expect(await screen.findByRole('heading', { level: 1, name: 'Chania, au rythme de la mer.' })).toBeInTheDocument()
    expect(document.querySelector('a[href*="/days/"]')).toBeNull()
  })

  it('does not pretend to accept the demo quote', async () => {
    renderAt('/quotes/NV-2026-0182')

    expect(await screen.findByRole('button', { name: 'Accept the offer' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Decline the offer' })).toBeDisabled()
    expect(screen.getByText(/Answering an offer is coming soon/)).toBeInTheDocument()
  })

  it.each(['/trips', '/plans/chania', '/quotes/NV-2026-0182', '/agent'])(
    'says %s shows demo data',
    async (url) => {
      renderAt(url)

      expect(await screen.findByRole('note')).toHaveTextContent('Demo data.')
    },
  )

  it.each(['/trips', '/admin/partners', '/agent', '/settings', '/wish', '/plans/chania', '/quotes/NV-2026-0182'])(
    'ends %s with the site footer',
    async (url) => {
      renderAt(url)

      const footer = await screen.findByRole('contentinfo', {}, { timeout: 3000 })
      expect(screen.getAllByRole('contentinfo')).toHaveLength(1)
      expect(within(footer).getByRole('link', { name: 'Legal notices' })).toHaveAttribute('href', '/legal')
      expect(within(footer).getByRole('link', { name: 'Destinations and reviews' })).toHaveAttribute(
        'href',
        '/destinations',
      )
      expect(within(footer).getByRole('group', { name: 'Language' })).toBeInTheDocument()
    },
  )

  it('does not show a concierge chat on the plan or on trips', async () => {
    renderAt('/plans/chania')

    expect(await screen.findByRole('note')).toHaveTextContent('Demo data.')
    expect(screen.queryByRole('button', { name: 'Open the conversation' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send' })).not.toBeInTheDocument()
    expect(screen.queryByText(/messages can't be sent yet/)).not.toBeInTheDocument()

    renderAt('/trips')

    expect(await screen.findByRole('heading', { name: 'My previews' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Open the conversation' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send' })).not.toBeInTheDocument()
    expect(screen.queryByText(/\d+ messages?/)).not.toBeInTheDocument()
  })

  it('does not let an agent take a demo request', async () => {
    me = { ...ADMIN, role: 'agent' }
    renderAt('/agent')

    const buttons = await screen.findAllByRole('button', { name: 'Take the plan' })
    for (const button of buttons) expect(button).toBeDisabled()
  })

  it('names the preview version once in the trip panel', async () => {
    renderAt('/trips')

    const panel = await screen.findByRole('region', { name: /^Trip: Chania/ })

    expect(within(panel).getAllByText(/^Preview v\d+$/)).toHaveLength(1)
  })

  it('shows the chosen trip', async () => {
    renderAt('/trips')

    fireEvent.click(await screen.findByRole('button', { name: /Marrakech, derrière les portes/ }))

    expect(await screen.findByRole('region', { name: 'Trip: Marrakech, derrière les portes' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send' })).not.toBeInTheDocument()
  })
})
