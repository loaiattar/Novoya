import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse, Plan } from '../api/generated/types.gen'
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

const OFFER_ID = '00000000-0000-4000-8000-000000000041'

// What GET /offers/{id} answers, plus a partner name it must never show if one ever leaks in.
const OFFER = {
  id: OFFER_ID,
  kind: 'hotel',
  title: 'Chambre double sur le port',
  description: 'Une chambre inventée face à la mer.',
  country: 'Greece',
  city: 'Chania',
  min_persons: 1,
  max_persons: 2,
  available_from: '2026-11-01',
  available_to: '2027-10-31',
  price_eur: 85,
  price_unit: 'person/night',
  opening_months: [5, 6, 9],
  conditions: 'Petit-déjeuner inclus',
  restrictions: 'Non-fumeur',
  cancellation: "Gratuite jusqu'à 7 jours avant",
  confirmation_delay_hours: 24,
  tags: ['accommodation:stay'],
  partner_name: 'Maison Zéphyr Inventée',
}

let me: MeResponse
let signedIn: boolean
let offerAnswer: () => Response

const PLAN_ID = '00000000-0000-4000-8000-000000000020'

const PLAN: Plan = {
  id: PLAN_ID,
  wish_id: '00000000-0000-4000-8000-000000000010',
  status: 'proposed',
  based_on_preferences: true,
  summary: 'Une semaine inventée au bord de la mer.',
  items: [
    {
      id: 'i1',
      offer_id: OFFER_ID,
      day: 1,
      quantity: 2,
      note: null,
      kind: 'hotel',
      title: OFFER.title,
      description: OFFER.description,
      available: true,
    },
  ],
}

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    if (path === '/me') {
      return signedIn ? Response.json(me) : Response.json({ code: 'unauthenticated', detail: 'no session' }, { status: 401 })
    }
    if (path === `/offers/${OFFER_ID}`) return offerAnswer()
    if (path === `/plans/${PLAN_ID}`) return Response.json(PLAN)
    return Response.json({ code: 'offer_not_found', detail: 'no offer' }, { status: 404 })
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
  return { router }
}

describe('offer page', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    me = CLIENT
    signedIn = true
    offerAnswer = () => Response.json(OFFER)
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('shows the offer title and description', async () => {
    renderAt(`/offers/${OFFER_ID}`)

    expect(await screen.findByRole('heading', { level: 1, name: OFFER.title })).toBeInTheDocument()
    expect(screen.getByText(OFFER.description)).toBeInTheDocument()
  })

  it('labels the price as indicative, per person and night', async () => {
    renderAt(`/offers/${OFFER_ID}`)

    await screen.findByRole('heading', { level: 1, name: OFFER.title })
    expect(screen.getByText(/indicative/i)).toBeInTheDocument()
    expect(document.body.textContent).toContain('€85')
    expect(document.body.textContent).toMatch(/per person/i)
    expect(document.body.textContent).toMatch(/night/i)
  })

  it('lists the opening months by name', async () => {
    renderAt(`/offers/${OFFER_ID}`)

    await screen.findByRole('heading', { level: 1, name: OFFER.title })
    for (const month of ['May', 'June', 'September']) {
      expect(document.body.textContent).toContain(month)
    }
    expect(document.body.textContent).not.toContain('January')
  })

  it('shows the conditions, restrictions and cancellation terms', async () => {
    renderAt(`/offers/${OFFER_ID}`)

    expect(await screen.findByText(OFFER.conditions)).toBeInTheDocument()
    expect(screen.getByText(OFFER.restrictions)).toBeInTheDocument()
    expect(screen.getByText(OFFER.cancellation)).toBeInTheDocument()
  })

  it('never shows the partner name', async () => {
    renderAt(`/offers/${OFFER_ID}`)

    await screen.findByRole('heading', { level: 1, name: OFFER.title })
    expect(document.body.textContent).not.toContain(OFFER.partner_name)
  })

  it('says so when the offer does not exist', async () => {
    renderAt('/offers/00000000-0000-4000-8000-000000000099')

    expect(await screen.findByText(/doesn't exist/i)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 1, name: OFFER.title })).not.toBeInTheDocument()
  })

  it('opens the offer from its day on the plan, and the plan still shows no price', async () => {
    renderAt(`/plans/${PLAN_ID}`)

    const link = await screen.findByRole('link', { name: new RegExp(OFFER.title) })
    expect(link).toHaveAttribute('href', `/offers/${OFFER_ID}`)
    expect(document.body.textContent).not.toContain('€')
  })

  it('names the price box by its label', async () => {
    renderAt(`/offers/${OFFER_ID}`)

    expect(await screen.findByRole('complementary', { name: 'Indicative price' })).toBeInTheDocument()
  })

  it('says the price comes in the quote when the offer has none', async () => {
    offerAnswer = () => Response.json({ ...OFFER, price_eur: null, price_unit: null })
    renderAt(`/offers/${OFFER_ID}`)

    expect(await screen.findByText('The price will come in your quote.')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('€')
  })

  it('says an exact group size and an immediate confirmation plainly', async () => {
    offerAnswer = () => Response.json({ ...OFFER, min_persons: 2, max_persons: 2, confirmation_delay_hours: 0 })
    renderAt(`/offers/${OFFER_ID}`)

    expect(await screen.findByText('2 people')).toBeInTheDocument()
    expect(screen.getByText('Immediate')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('2 to 2')
    expect(document.body.textContent).not.toContain('0 hours')
  })

  it('shows the offer in French: country, months and price', async () => {
    me = { ...CLIENT, locale: 'fr' }
    renderAt(`/offers/${OFFER_ID}`)

    await screen.findByRole('heading', { level: 1, name: OFFER.title })
    const text = (document.body.textContent ?? '').replace(/[\u00a0\u202f]/g, ' ')
    expect(text).toContain('Chania, Grèce')
    expect(text).toContain('85 €')
    expect(text).toContain('par personne et par nuit')
    for (const month of ['mai', 'juin', 'septembre']) expect(text).toContain(month)
    expect(screen.getByText('Prix indicatif')).toBeInTheDocument()
  })

  it('says the offer details are in French when the page is in English', async () => {
    renderAt(`/offers/${OFFER_ID}`)

    const title = await screen.findByRole('heading', { level: 1, name: OFFER.title })
    expect(screen.getByText('Offer details are in French')).toBeInTheDocument()
    // Screen readers read the partner's texts with a French voice.
    expect(title).toHaveAttribute('lang', 'fr')
    for (const text of [OFFER.description, OFFER.conditions, OFFER.restrictions, OFFER.cancellation]) {
      expect(screen.getByText(text)).toHaveAttribute('lang', 'fr')
    }
  })

  it('has no language note when the page is in French', async () => {
    me = { ...CLIENT, locale: 'fr' }
    renderAt(`/offers/${OFFER_ID}`)

    await screen.findByRole('heading', { level: 1, name: OFFER.title })
    expect(screen.queryByText('Offer details are in French')).not.toBeInTheDocument()
    expect(screen.queryByText(/en français/i)).not.toBeInTheDocument()
  })

  it('says the offer does not exist for an id that is no offer id', async () => {
    offerAnswer = () => Response.json({ code: 'invalid_input', detail: 'offer_id: not a UUID' }, { status: 422 })
    renderAt(`/offers/${OFFER_ID}`)

    expect(await screen.findByText(/doesn't exist/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('sends to the sign-in page when the session ended, to come back after', async () => {
    offerAnswer = () => {
      signedIn = false
      return Response.json({ code: 'unauthenticated', detail: 'no session' }, { status: 401 })
    }
    const { router } = renderAt(`/offers/${OFFER_ID}`)

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: `/offers/${OFFER_ID}` })
  })
})
