import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse, OfferResponse, PartnerResponse } from '../api/generated/types.gen'
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

// Added by hand: fully editable.
const RIAD: PartnerResponse = {
  id: '00000000-0000-4000-8000-000000000101',
  name: 'Riad Lune',
  kind: 'hotel',
  country: 'Morocco',
  city: 'Fès',
  contact_email: 'hello@riad-lune.example',
  contact_phone: '+212 600 000 000',
  active: true,
  hidden: false,
  imported: false,
}

// Imported from DÉTOUR: only hidden can change.
const ECUME: PartnerResponse = {
  id: '00000000-0000-4000-8000-000000000102',
  name: 'Maison Écume',
  kind: 'hotel',
  country: 'France',
  city: 'Sète',
  contact_email: 'bonjour@ecume.example',
  contact_phone: null,
  active: true,
  hidden: false,
  imported: true,
}

// Added by hand, closed and hidden: the admin list still shows it.
const LODGE: PartnerResponse = {
  id: '00000000-0000-4000-8000-000000000103',
  name: 'Lodge Nord',
  kind: 'guide',
  country: 'Norway',
  city: 'Tromsø',
  contact_email: 'post@lodge-nord.example',
  contact_phone: null,
  active: false,
  hidden: true,
  imported: false,
}

const PATIO: OfferResponse = {
  id: '00000000-0000-4000-8000-000000000201',
  partner_id: RIAD.id,
  kind: 'hotel',
  title: 'Patio room',
  description: 'Two beds on the patio.',
  country: 'Morocco',
  city: 'Fès',
  min_persons: 1,
  max_persons: 3,
  available_from: '2027-03-01',
  available_to: '2027-10-31',
  tags: ['style:riad'],
  featured: false,
  active: true,
  price_eur: 85,
  price_unit: 'person/night',
  opening_months: [3, 4, 10],
  conditions: 'Breakfast included.',
  restrictions: null,
  cancellation: null,
  confirmation_delay_hours: 24,
  hidden: false,
}

const ETANG: OfferResponse = {
  ...PATIO,
  id: '00000000-0000-4000-8000-000000000202',
  partner_id: ECUME.id,
  title: 'Chambre vue étang',
  description: 'Une chambre face à l’étang.',
  country: 'France',
  city: 'Sète',
  tags: ['style:sea'],
  price_eur: null,
  price_unit: null,
  opening_months: [],
  conditions: null,
  confirmation_delay_hours: null,
}

const NEW_ID = '00000000-0000-4000-8000-000000000301'
const UNKNOWN_ID = '00000000-0000-4000-8000-000000000399'

type Answer = (body: unknown) => Response | Promise<Response>

let me: MeResponse
let partners: PartnerResponse[]
let offers: OfferResponse[]
let partnersAnswer: () => Response | Promise<Response>
let saveAnswer: Answer | undefined
let requests: { method: string; path: string; search: string; body?: unknown }[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    const body = request.method === 'GET' ? undefined : await request.clone().json().catch(() => undefined)
    requests.push({ method: request.method, path: url.pathname, search: url.search, body })
    if (url.pathname === '/me') return Response.json(me)
    if (request.method !== 'GET' && saveAnswer) return saveAnswer(body)
    if (url.pathname === '/admin/partners' && request.method === 'GET') return partnersAnswer()
    if (url.pathname === '/admin/partners' && request.method === 'POST') {
      const created = { ...(body as PartnerResponse), id: NEW_ID, hidden: false, imported: false, contact_phone: null }
      partners = [...partners, created]
      return Response.json(created, { status: 201 })
    }
    const partner = url.pathname.match(/^\/admin\/partners\/([^/]+)$/)
    if (partner && request.method === 'PATCH') {
      partners = partners.map((row) => (row.id === partner[1] ? { ...row, ...(body as object) } : row))
      return Response.json(partners.find((row) => row.id === partner[1]))
    }
    if (url.pathname === '/admin/offers' && request.method === 'GET') {
      const partnerId = url.searchParams.get('partner_id')
      return Response.json(partnerId ? offers.filter((row) => row.partner_id === partnerId) : offers)
    }
    if (url.pathname === '/admin/offers' && request.method === 'POST') {
      const created = { ...PATIO, ...(body as object), id: '00000000-0000-4000-8000-000000000302' }
      offers = [...offers, created]
      return Response.json(created, { status: 201 })
    }
    const offer = url.pathname.match(/^\/admin\/offers\/([^/]+)$/)
    if (offer && request.method === 'PATCH') {
      offers = offers.map((row) => (row.id === offer[1] ? { ...row, ...(body as object) } : row))
      return Response.json(offers.find((row) => row.id === offer[1]))
    }
    return Response.json({ code: 'not_found', detail: 'no route' }, { status: 404 })
  })
}

const sent = (method: string, path: string) => requests.filter((request) => request.method === method && request.path === path)
const writes = () => requests.filter((request) => request.method !== 'GET')

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

const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })

describe('admin partners and offers', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    me = ADMIN
    partners = [LODGE, ECUME, RIAD]
    offers = [PATIO, ETANG]
    partnersAnswer = () => Response.json(partners)
    saveAnswer = undefined
    requests = []
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('lists every partner for an admin, the imported one marked DÉTOUR', async () => {
    renderAt('/admin/partners')

    // The first render of the admin chunk can be slow on a cold start.
    const table = await screen.findByRole('table', { name: 'Partners and their status' }, { timeout: 3000 })
    expect(screen.getByRole('heading', { level: 1, name: 'Partners' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Partners' })).toHaveAttribute('aria-current', 'page')
    const ecume = within(table).getByRole('rowheader', { name: /Maison Écume/ }).closest('tr') as HTMLElement
    expect(within(ecume).getByText('DÉTOUR')).toBeInTheDocument()
    const riad = within(table).getByRole('rowheader', { name: /Riad Lune/ }).closest('tr') as HTMLElement
    expect(within(riad).queryByText('DÉTOUR')).not.toBeInTheDocument()
    const lodge = within(table).getByRole('rowheader', { name: /Lodge Nord/ }).closest('tr') as HTMLElement
    expect(within(lodge).getByText('Inactive')).toBeInTheDocument()
    expect(within(lodge).getByText('Hidden')).toBeInTheDocument()
    expect(within(table).getByRole('link', { name: 'Riad Lune' })).toHaveAttribute('href', `/admin/partners/${RIAD.id}`)
  })

  it('searches the partners by city without accents and without a new request', async () => {
    renderAt('/admin/partners')
    const table = await screen.findByRole('table', { name: 'Partners and their status' }, { timeout: 3000 })

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search partners' }), { target: { value: 'SETE' } })

    await waitFor(() => expect(within(table).queryByRole('rowheader', { name: /Riad Lune/ })).not.toBeInTheDocument())
    expect(within(table).getByRole('rowheader', { name: /Maison Écume/ })).toBeInTheDocument()
    expect(within(table).queryByRole('rowheader', { name: /Lodge Nord/ })).not.toBeInTheDocument()
    expect(sent('GET', '/admin/partners')).toHaveLength(1)
  })

  it('keeps only the partners imported from DÉTOUR', async () => {
    renderAt('/admin/partners')
    const table = await screen.findByRole('table', { name: 'Partners and their status' }, { timeout: 3000 })

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by source' }), { target: { value: 'imported' } })

    await waitFor(() => expect(within(table).queryByRole('rowheader', { name: /Riad Lune/ })).not.toBeInTheDocument())
    expect(within(table).getByRole('rowheader', { name: /Maison Écume/ })).toBeInTheDocument()
    expect(within(table).queryByRole('rowheader', { name: /Lodge Nord/ })).not.toBeInTheDocument()
  })

  it.each([
    ['client', '/admin/partners'],
    ['client', `/admin/partners/${RIAD.id}`],
    ['agent', '/admin/partners'],
    ['agent', `/admin/partners/${RIAD.id}`],
  ] as const)('sends someone with the %s role away from %s', async (role, url) => {
    me = { ...ADMIN, role }
    const { router } = renderAt(url)

    await waitFor(() => expect(router.state.location.pathname).toBe('/wish'))
    expect(sent('GET', '/admin/partners')).toHaveLength(0)
  })

  it('creates a partner, then opens it', async () => {
    const { router } = renderAt('/admin/partners/new')
    expect(await screen.findByRole('heading', { level: 1, name: 'New partner' }, { timeout: 3000 })).toBeInTheDocument()

    fill('Name', ' Casa Azul ')
    fireEvent.change(screen.getByLabelText('Type'), { target: { value: 'activity' } })
    fill('Country', 'Portugal')
    fill('City', 'Porto')
    fill('Email', 'ola@casa-azul.example')
    fireEvent.click(screen.getByRole('button', { name: 'Create partner' }))

    await waitFor(() =>
      expect(sent('POST', '/admin/partners').map((request) => request.body)).toEqual([
        { name: 'Casa Azul', kind: 'activity', country: 'Portugal', city: 'Porto', contact_email: 'ola@casa-azul.example', active: true },
      ]),
    )
    await waitFor(() => expect(router.state.location.pathname).toBe(`/admin/partners/${NEW_ID}`))
  })

  it('does not send a partner with an invalid email', async () => {
    renderAt('/admin/partners/new')
    await screen.findByRole('heading', { level: 1, name: 'New partner' }, { timeout: 3000 })

    fill('Name', 'Casa Azul')
    fill('Country', 'Portugal')
    fill('City', 'Porto')
    fill('Email', 'ola@casa-azul')
    fireEvent.click(screen.getByRole('button', { name: 'Create partner' }))

    await waitFor(() => expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true'))
    expect(writes()).toHaveLength(0)
  })

  it('keeps the values and asks to check the fields when the API refuses them', async () => {
    saveAnswer = () => Response.json({ code: 'invalid_input', detail: 'city: too long' }, { status: 422 })
    renderAt('/admin/partners/new')
    await screen.findByRole('heading', { level: 1, name: 'New partner' }, { timeout: 3000 })

    fill('Name', 'Casa Azul')
    fill('Country', 'Portugal')
    fill('City', 'Porto')
    fill('Email', 'ola@casa-azul.example')
    fireEvent.click(screen.getByRole('button', { name: 'Create partner' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Some fields were refused. Check them and try again.')
    expect(screen.getByLabelText('Name')).toHaveValue('Casa Azul')
    expect(screen.getByLabelText('City')).toHaveValue('Porto')
  })

  it('saves every field of a hand-made partner', async () => {
    renderAt(`/admin/partners/${RIAD.id}`)
    expect(await screen.findByRole('heading', { level: 1, name: 'Riad Lune' }, { timeout: 3000 })).toBeInTheDocument()

    fill('Phone', '+212 611 111 111')
    fireEvent.click(screen.getByRole('button', { name: 'Save partner' }))

    await waitFor(() =>
      expect(sent('PATCH', `/admin/partners/${RIAD.id}`).map((request) => request.body)).toEqual([
        {
          name: 'Riad Lune',
          kind: 'hotel',
          country: 'Morocco',
          city: 'Fès',
          contact_email: 'hello@riad-lune.example',
          contact_phone: '+212 611 111 111',
          active: true,
          hidden: false,
        },
      ]),
    )
  })

  it('says DÉTOUR owns the row when the API answers imported_row', async () => {
    saveAnswer = () =>
      Response.json({ code: 'imported_row', detail: 'This row comes from DÉTOUR' }, { status: 409 })
    renderAt(`/admin/partners/${RIAD.id}`)
    await screen.findByRole('heading', { level: 1, name: 'Riad Lune' }, { timeout: 3000 })

    fill('City', 'Meknès')
    fireEvent.click(screen.getByRole('button', { name: 'Save partner' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/DÉTOUR/)
    expect(screen.getByLabelText('City')).toHaveValue('Meknès')
  })

  it('shows an imported partner read-only and only sends its hidden switch', async () => {
    renderAt(`/admin/partners/${ECUME.id}`)
    expect(await screen.findByRole('heading', { level: 1, name: 'Maison Écume' }, { timeout: 3000 })).toBeInTheDocument()

    expect(screen.getByText(/Change it in DÉTOUR/)).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveAttribute('readonly')
    expect(screen.getByLabelText('City')).toHaveAttribute('readonly')
    expect(screen.getByLabelText('Email')).toHaveAttribute('readonly')
    expect(screen.getByLabelText('Type')).toBeDisabled()
    expect(screen.queryByRole('link', { name: 'New offer' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('checkbox', { name: 'Hidden' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save partner' }))

    await waitFor(() =>
      expect(sent('PATCH', `/admin/partners/${ECUME.id}`).map((request) => request.body)).toEqual([{ hidden: true }]),
    )
  })

  it("lists only the partner's offers, read with partner_id", async () => {
    renderAt(`/admin/partners/${RIAD.id}`)

    const table = await screen.findByRole('table', { name: 'Offers of Riad Lune' }, { timeout: 3000 })
    expect(within(table).getByRole('link', { name: 'Patio room' })).toHaveAttribute(
      'href',
      `/admin/partners/${RIAD.id}/offers/${PATIO.id}`,
    )
    expect(within(table).queryByText('Chambre vue étang')).not.toBeInTheDocument()
    expect(requests).toContainEqual(
      expect.objectContaining({ method: 'GET', path: '/admin/offers', search: `?partner_id=${RIAD.id}` }),
    )
    expect(screen.getByRole('link', { name: 'New offer' })).toHaveAttribute('href', `/admin/partners/${RIAD.id}/offers/new`)
  })

  it('features an imported offer, sending only featured', async () => {
    renderAt(`/admin/partners/${ECUME.id}`)

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Featured: Chambre vue étang' }, { timeout: 3000 }))

    await waitFor(() =>
      expect(sent('PATCH', `/admin/offers/${ETANG.id}`).map((request) => request.body)).toEqual([{ featured: true }]),
    )
  })

  it('creates an offer with normalized tags, sorted months and a price with its unit', async () => {
    const { router } = renderAt(`/admin/partners/${RIAD.id}/offers/new`)
    expect(await screen.findByRole('heading', { level: 1, name: 'New offer' }, { timeout: 3000 })).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Type'), { target: { value: 'activity' } })
    fill('Title', 'Zellige workshop')
    fill('Description', 'A morning with a tile maker.')
    fill('Country', 'Morocco')
    fill('City', 'Fès')
    fill('Fewest persons', '2')
    fill('Most persons', '6')
    fill('Available from', '2027-03-01')
    fill('Available to', '2027-10-31')
    fill('Tags', 'Craft:Zellige, craft:zellige mood:calm')
    fireEvent.click(screen.getByRole('checkbox', { name: 'Featured' }))
    fill('Price (€)', '40')
    fireEvent.change(screen.getByLabelText('Price unit'), { target: { value: 'person/activity' } })
    const months = screen.getByRole('group', { name: 'Opening months' })
    fireEvent.click(within(months).getByRole('checkbox', { name: 'October' }))
    fireEvent.click(within(months).getByRole('checkbox', { name: 'March' }))
    fireEvent.click(within(months).getByRole('checkbox', { name: 'April' }))
    fill('Conditions', 'Closed shoes.')
    fill('Confirmation delay (hours)', '48')
    fireEvent.click(screen.getByRole('button', { name: 'Create offer' }))

    await waitFor(() =>
      expect(sent('POST', '/admin/offers').map((request) => request.body)).toEqual([
        {
          partner_id: RIAD.id,
          kind: 'activity',
          title: 'Zellige workshop',
          description: 'A morning with a tile maker.',
          country: 'Morocco',
          city: 'Fès',
          min_persons: 2,
          max_persons: 6,
          available_from: '2027-03-01',
          available_to: '2027-10-31',
          tags: ['craft:zellige', 'mood:calm'],
          featured: true,
          active: true,
          price_eur: 40,
          price_unit: 'person/activity',
          opening_months: [3, 4, 10],
          conditions: 'Closed shoes.',
          restrictions: null,
          cancellation: null,
          confirmation_delay_hours: 48,
        },
      ]),
    )
    await waitFor(() => expect(router.state.location.pathname).toBe(`/admin/partners/${RIAD.id}`))
  })

  it('does not send an offer with a tag that is not section:tag', async () => {
    renderAt(`/admin/partners/${RIAD.id}/offers/${PATIO.id}`)
    await screen.findByRole('heading', { level: 1, name: 'Patio room' }, { timeout: 3000 })

    fill('Tags', 'style:riad, calm')
    fireEvent.click(screen.getByRole('button', { name: 'Save offer' }))

    await waitFor(() => expect(screen.getByLabelText('Tags')).toHaveAttribute('aria-invalid', 'true'))
    expect(writes()).toHaveLength(0)
  })

  it('does not send a price without its unit', async () => {
    renderAt(`/admin/partners/${RIAD.id}/offers/${PATIO.id}`)
    await screen.findByRole('heading', { level: 1, name: 'Patio room' }, { timeout: 3000 })

    fireEvent.change(screen.getByLabelText('Price unit'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save offer' }))

    await waitFor(() => expect(screen.getByLabelText('Price unit')).toHaveAttribute('aria-invalid', 'true'))
    expect(writes()).toHaveLength(0)
  })

  it('clears the price of a hand-made offer with its unit', async () => {
    renderAt(`/admin/partners/${RIAD.id}/offers/${PATIO.id}`)
    await screen.findByRole('heading', { level: 1, name: 'Patio room' }, { timeout: 3000 })

    fill('Price (€)', '')
    fireEvent.change(screen.getByLabelText('Price unit'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save offer' }))

    await waitFor(() =>
      expect(sent('PATCH', `/admin/offers/${PATIO.id}`).map((request) => request.body)).toEqual([
        expect.objectContaining({ title: 'Patio room', price_eur: null, price_unit: null }),
      ]),
    )
  })

  it('shows an offer of an imported partner read-only', async () => {
    renderAt(`/admin/partners/${ECUME.id}/offers/${ETANG.id}`)
    await screen.findByRole('heading', { level: 1, name: 'Chambre vue étang' }, { timeout: 3000 })

    expect(screen.getByText(/Change it in DÉTOUR/)).toBeInTheDocument()
    expect(screen.getByLabelText('Title')).toHaveAttribute('readonly')
    expect(screen.getByLabelText('Tags')).toHaveAttribute('readonly')
    expect(screen.getByRole('checkbox', { name: 'Featured' })).toBeEnabled()
  })

  it("says so when the partner doesn't exist", async () => {
    renderAt(`/admin/partners/${UNKNOWN_ID}`)

    expect(await screen.findByText("This partner doesn't exist.", undefined, { timeout: 3000 })).toBeInTheDocument()
  })

  it('lets the admin try again when the partners could not be loaded', async () => {
    partnersAnswer = () => Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
    renderAt('/admin/partners')

    expect(await screen.findByText('The partners could not be loaded.', undefined, { timeout: 3000 })).toBeInTheDocument()
    partnersAnswer = () => Response.json(partners)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('rowheader', { name: /Riad Lune/ })).toBeInTheDocument()
  })

  it("shows the partners in the admin's language", async () => {
    me = { ...ADMIN, locale: 'fr' }
    renderAt('/admin/partners')

    expect(await screen.findByRole('heading', { level: 1, name: 'Partenaires' }, { timeout: 3000 })).toBeInTheDocument()
    expect(await screen.findByRole('table', { name: 'Partenaires et leur statut' })).toBeInTheDocument()
    expect(screen.getByRole('searchbox', { name: 'Rechercher un partenaire' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Filtrer par source' })).toHaveDisplayValue('Toutes les sources')
    expect(screen.getByRole('link', { name: 'Nouveau partenaire' })).toHaveAttribute('href', '/admin/partners/new')
    expect(document.documentElement).toHaveAttribute('lang', 'fr')
  })
  it.each([
    ['/admin', 'Users', 'Partners'],
    [`/admin/partners/${RIAD.id}`, 'Partners', 'Users'],
  ])('marks the open section in the admin nav on %s', async (url, current, other) => {
    renderAt(url)

    await waitFor(() => expect(screen.getByRole('link', { name: current })).toHaveAttribute('aria-current', 'page'), {
      timeout: 3000,
    })
    expect(screen.getByRole('link', { name: other })).not.toHaveAttribute('aria-current')
  })

  it('opens a partner just created even when the partners cannot be read again', async () => {
    const { router } = renderAt('/admin/partners/new')
    await screen.findByRole('heading', { level: 1, name: 'New partner' }, { timeout: 3000 })
    partnersAnswer = () => Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })

    fill('Name', 'Casa Azul')
    fill('Country', 'Portugal')
    fill('City', 'Porto')
    fill('Email', 'ola@casa-azul.example')
    fireEvent.click(screen.getByRole('button', { name: 'Create partner' }))

    await waitFor(() => expect(router.state.location.pathname).toBe(`/admin/partners/${NEW_ID}`))
    expect(await screen.findByRole('heading', { level: 1, name: 'Casa Azul' })).toBeInTheDocument()
    expect(screen.queryByText("This partner doesn't exist.")).not.toBeInTheDocument()
  })

  it('says the partner or offer is gone when the API answers 404 on save', async () => {
    saveAnswer = () => Response.json({ code: 'partner_not_found', detail: 'gone' }, { status: 404 })
    renderAt(`/admin/partners/${RIAD.id}`)
    await screen.findByRole('heading', { level: 1, name: 'Riad Lune' }, { timeout: 3000 })

    fireEvent.click(screen.getByRole('button', { name: 'Save partner' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('This partner or offer no longer exists.')
  })

  it('hides an offer from the table, sending only hidden', async () => {
    renderAt(`/admin/partners/${RIAD.id}`)

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Hidden: Patio room' }, { timeout: 3000 }))

    await waitFor(() =>
      expect(sent('PATCH', `/admin/offers/${PATIO.id}`).map((request) => request.body)).toEqual([{ hidden: true }]),
    )
  })

  it('still says a switch failed when another one succeeds meanwhile', async () => {
    const GARDEN: OfferResponse = { ...PATIO, id: '00000000-0000-4000-8000-000000000203', title: 'Garden room' }
    offers = [PATIO, GARDEN, ETANG]
    saveAnswer = (body) =>
      'featured' in (body as object)
        ? Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
        : Response.json({ ...GARDEN, hidden: true })
    renderAt(`/admin/partners/${RIAD.id}`)

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Featured: Patio room' }, { timeout: 3000 }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Hidden: Garden room' }))

    await waitFor(() => expect(sent('PATCH', `/admin/offers/${GARDEN.id}`)).toHaveLength(1))
    expect(await screen.findByRole('alert')).toHaveTextContent('The change could not be saved. Please try again.')
  })

  it('saves only featured and hidden from the form of an imported offer', async () => {
    renderAt(`/admin/partners/${ECUME.id}/offers/${ETANG.id}`)
    await screen.findByRole('heading', { level: 1, name: 'Chambre vue étang' }, { timeout: 3000 })

    fireEvent.click(screen.getByRole('checkbox', { name: 'Featured' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save offer' }))

    await waitFor(() =>
      expect(sent('PATCH', `/admin/offers/${ETANG.id}`).map((request) => request.body)).toEqual([
        { featured: true, hidden: false },
      ]),
    )
  })

  it('keeps the offer values and asks to check the fields when the API refuses them', async () => {
    saveAnswer = () => Response.json({ code: 'invalid_offer', detail: 'bad' }, { status: 422 })
    renderAt(`/admin/partners/${RIAD.id}/offers/${PATIO.id}`)
    await screen.findByRole('heading', { level: 1, name: 'Patio room' }, { timeout: 3000 })

    fill('Title', 'Patio suite')
    fireEvent.click(screen.getByRole('button', { name: 'Save offer' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Some fields were refused. Check them and try again.')
    expect(screen.getByLabelText('Title')).toHaveValue('Patio suite')
  })

  it.each([
    ['an unknown offer', `/admin/partners/${RIAD.id}/offers/${UNKNOWN_ID}`],
    ["another partner's offer", `/admin/partners/${RIAD.id}/offers/${ETANG.id}`],
  ])("says so for %s", async (_name, url) => {
    renderAt(url)

    expect(await screen.findByText("This offer doesn't exist.", undefined, { timeout: 3000 })).toBeInTheDocument()
  })

  it('sends to DÉTOUR for a new offer of an imported partner', async () => {
    renderAt(`/admin/partners/${ECUME.id}/offers/new`)

    expect(
      await screen.findByText('The offers of this partner come from DÉTOUR: add them there.', undefined, { timeout: 3000 }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create offer' })).not.toBeInTheDocument()
  })
})
