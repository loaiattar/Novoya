import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse, PanelLimitsOut, PlanResponse, WishResponse } from '../api/generated/types.gen'
import { type CachedWish, wishQueryKey } from '../api/wishes'
import { createAppRouter } from '../router'

// The preferences page and the catalogue limits of the wish destination (#183): the travellers
// stepper and the date inputs follow GET /wishes/{id}/limits, and the page says before sending
// when no offer fits the travellers and the dates.

const CAMILLE: MeResponse = {
  id: '6f1c2b1e-0000-4000-8000-000000000002',
  email: 'camille@exemple.fr',
  name: 'Camille Martin',
  first_name: 'Camille',
  last_name: 'Martin',
  role: 'client',
  locale: 'en',
  status: 'active',
  email_verified: true,
  created_at: '2026-10-01T10:00:00Z',
  sign_in_methods: ['password'],
}

const WISH_ID = '0b5f8a52-0000-4000-8000-000000000010'
const LIMITS_PATH = `/wishes/${WISH_ID}/limits`
const ANSWERS_PATH = `/wishes/${WISH_ID}/answers`
const CLOSEST_PATH = `/wishes/${WISH_ID}/closest-dates`
const CUSTOM_PATH = `/wishes/${WISH_ID}/custom-request`
const CUSTOM_PLAN_ID = '0b5f8a52-0000-4000-8000-000000000030'

const PANEL_WISH: WishResponse = {
  id: WISH_ID,
  status: 'panel_shown',
  destination: { country: 'Greece', city: 'Chania' },
  suggestions: [],
  panel: {
    ask_budget: true,
    ask_persons: true,
    ask_dates: true,
    sections: [
      {
        id: 'mood',
        title: 'Ambiance',
        multi: true,
        tags: [{ id: 'calm', label: 'Calme', preselected: true }],
      },
    ],
  },
}

const PLAN: PlanResponse = {
  id: '0b5f8a52-0000-4000-8000-000000000020',
  wish_id: WISH_ID,
  status: 'proposed',
  based_on_preferences: true,
  summary: 'Une semaine calme à Chania',
  items: [],
}

// Offers at Chania from May to July 2027, for 1 to 8 travellers.
const LIMITS: PanelLimitsOut = {
  persons_min: 1,
  persons_max: 8,
  first_date: '2027-05-01',
  last_date: '2027-07-31',
  open_months: [5, 6, 7],
  fits: null,
}

// "Today" for the whole file: the date inputs compare with it.
const TODAY = '2026-10-23'

type Call = { method: string; path: string; search: URLSearchParams; body: unknown }

let signedIn: MeResponse
let calls: Call[]
let limits: PanelLimitsOut
// The answer to GET /limits without parameters (the limits) and with them (the fit check).
let limitsAnswer: () => Response | Promise<Response>
let fitAnswer: (search: URLSearchParams) => Response | Promise<Response>

/** The fit rule of the mock: the trip must start and end inside the offers' months (May to July 2027). */
const fitsInSummer = (search: URLSearchParams) =>
  Response.json({
    ...limits,
    fits: search.get('start_date')! >= '2027-05-01' && search.get('end_date')! <= '2027-07-31',
  })

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    const text = request.method === 'POST' ? await request.text() : ''
    calls.push({ method: request.method, path: url.pathname, search: url.searchParams, body: text ? JSON.parse(text) : undefined })
    if (url.pathname === '/me') return Response.json(signedIn)
    if (url.pathname === LIMITS_PATH) return url.searchParams.has('persons') ? fitAnswer(url.searchParams) : limitsAnswer()
    if (url.pathname === ANSWERS_PATH) return Response.json(PLAN, { status: 201 })
    // The nearest summer trip of the same length (#184).
    if (url.pathname === CLOSEST_PATH)
      return Response.json([{ start_date: '2027-05-01', end_date: '2027-05-08', offers: 3 }])
    if (url.pathname === CUSTOM_PATH)
      return Response.json({ id: CUSTOM_PLAN_ID, wish_id: WISH_ID, status: 'requested' }, { status: 201 })
    return Response.json({ status: 'ok' })
  })
}

function renderPreferences(wish: WishResponse = PANEL_WISH) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData<CachedWish>(wishQueryKey(WISH_ID), { ...wish, text: 'Une semaine à Chania' })
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [`/wish/${WISH_ID}/preferences`] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router }
}

const limitsReads = () => calls.filter((call) => call.method === 'GET' && call.path === LIMITS_PATH)
const plainLimitsReads = () => limitsReads().filter((call) => !call.search.has('persons'))
const fitReads = () => limitsReads().filter((call) => call.search.has('persons'))
const answerPosts = () => calls.filter((call) => call.method === 'POST' && call.path === ANSWERS_PATH)
const customPosts = () => calls.filter((call) => call.method === 'POST' && call.path === CUSTOM_PATH)

/** Waits until the page has the limits in hand (the stepper shows their bounds). */
async function openPanel() {
  await screen.findByRole('heading', { name: /What matters/ })
  await waitFor(() => expect(plainLimitsReads()).toHaveLength(1))
}

function fill(dates: { start: string; end: string }) {
  fireEvent.change(screen.getByLabelText(/Maximum budget/), { target: { value: '3 500 €' } })
  fireEvent.change(screen.getByLabelText('Departure'), { target: { value: dates.start } })
  fireEvent.change(screen.getByLabelText('Return'), { target: { value: dates.end } })
}

const WINTER = { start: '2027-01-10', end: '2027-01-17' } // no offer open
const SUMMER = { start: '2027-05-12', end: '2027-05-19' } // fits

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(`${TODAY}T10:00:00`))
  client.setConfig({ baseUrl: 'http://api.test' })
  signedIn = CAMILLE
  calls = []
  limits = LIMITS
  limitsAnswer = () => Response.json(limits)
  fitAnswer = fitsInSummer
  mockApi()
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('the preferences panel within the catalogue limits', () => {
  it('reads the limits of the destination when the panel opens', async () => {
    renderPreferences()

    await screen.findByRole('heading', { name: /What matters/ })

    await waitFor(() => expect(plainLimitsReads()).toHaveLength(1))
    expect([...plainLimitsReads()[0]!.search.keys()]).toEqual([])
  })

  it('starts the travellers inside the limits and stops the stepper at them', async () => {
    limits = { ...LIMITS, persons_min: 4, persons_max: 5 }
    renderPreferences()
    await openPanel()

    // The usual start of 2 travellers is raised to the smallest group an offer takes.
    expect(await screen.findByText('4 travellers')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'One traveller fewer' })).toHaveAttribute('aria-disabled', 'true')

    fireEvent.click(screen.getByRole('button', { name: 'One more traveller' }))
    expect(screen.getByText('5 travellers')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'One more traveller' })).toHaveAttribute('aria-disabled', 'true')

    fireEvent.click(screen.getByRole('button', { name: 'One more traveller' }))
    expect(screen.getByText('5 travellers')).toBeInTheDocument()
  })

  it('lowers the starting travellers to the largest group an offer takes', async () => {
    limits = { ...LIMITS, persons_min: 1, persons_max: 1 }
    renderPreferences()
    await openPanel()

    expect(await screen.findByText('1 traveller')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'One traveller fewer' })).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByRole('button', { name: 'One more traveller' })).toHaveAttribute('aria-disabled', 'true')
  })

  // The plan needs one open day in the trip (#182): the pickers allow every trip that overlaps
  // the offers' season, so the departure goes up to the last open day and the return starts at
  // the first one (review of #189).
  it('lets the trip overlap the offers: departure up to the last open day, return from the first', async () => {
    renderPreferences()
    await openPanel()

    await waitFor(() => expect(screen.getByLabelText('Departure')).toHaveAttribute('max', '2027-07-31'))
    expect(screen.getByLabelText('Departure')).toHaveAttribute('min', TODAY)
    expect(screen.getByLabelText('Return')).toHaveAttribute('min', '2027-05-01')
    expect(screen.getByLabelText('Return')).not.toHaveAttribute('max')
  })

  it('offers dates from today when the first offer day is past', async () => {
    limits = { ...LIMITS, first_date: '2026-03-01', last_date: '2027-07-31' }
    renderPreferences()
    await openPanel()

    await waitFor(() => expect(screen.getByLabelText('Departure')).toHaveAttribute('max', '2027-07-31'))
    expect(screen.getByLabelText('Departure')).toHaveAttribute('min', TODAY)
    expect(screen.getByLabelText('Return')).toHaveAttribute('min', TODAY)
  })

  it('keeps the return after the departure within the limits', async () => {
    renderPreferences()
    await openPanel()

    fireEvent.change(screen.getByLabelText('Departure'), { target: { value: '2027-06-02' } })

    expect(screen.getByLabelText('Return')).toHaveAttribute('min', '2027-06-02')
    expect(screen.getByLabelText('Return')).not.toHaveAttribute('max')
  })

  it('lets a trip depart before the first open day if it returns in the season', async () => {
    renderPreferences()
    await openPanel()
    await waitFor(() => expect(screen.getByLabelText('Departure')).toHaveAttribute('max', '2027-07-31'))

    fireEvent.change(screen.getByLabelText('Departure'), { target: { value: '2027-04-30' } })

    expect(screen.getByLabelText('Return')).toHaveAttribute('min', '2027-05-01')
  })

  it('checks once when the travellers change quickly', async () => {
    // Review of #189: each click used to send its own check.
    renderPreferences()
    await openPanel()
    fill(SUMMER)
    await waitFor(() => expect(fitReads()).toHaveLength(1))

    const more = screen.getByRole('button', { name: 'One more traveller' })
    for (let click = 0; click < 5; click++) fireEvent.click(more)

    await waitFor(() => expect(fitReads()).toHaveLength(2))
    expect(fitReads()[1]!.search.get('persons')).toBe('7')
    await new Promise((resolve) => setTimeout(resolve, 400))
    expect(fitReads()).toHaveLength(2)
  })

  it('keeps the usual bounds and still sends when the limits cannot be read', async () => {
    limitsAnswer = () => Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
    renderPreferences()
    await openPanel()

    fireEvent.click(screen.getByRole('button', { name: 'One traveller fewer' }))
    expect(screen.getByText('1 traveller')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'One traveller fewer' })).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByLabelText('Departure')).toHaveAttribute('min', TODAY)
    expect(screen.getByLabelText('Departure')).not.toHaveAttribute('max')
    expect(screen.getByLabelText('Return')).not.toHaveAttribute('max')

    fill(SUMMER)
    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    await waitFor(() => expect(answerPosts()).toHaveLength(1))
  })

  it('keeps the usual bounds when the destination has no listed offer', async () => {
    limits = { persons_min: null, persons_max: null, first_date: null, last_date: null, open_months: [], fits: null }
    renderPreferences()
    await openPanel()

    expect(screen.getByText('2 travellers')).toBeInTheDocument()
    for (let click = 0; click < 48; click++) fireEvent.click(screen.getByRole('button', { name: 'One more traveller' }))
    expect(screen.getByText('50 travellers')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'One more traveller' })).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByLabelText('Departure')).toHaveAttribute('min', TODAY)
    expect(screen.getByLabelText('Departure')).not.toHaveAttribute('max')
    expect(screen.getByLabelText('Return')).not.toHaveAttribute('max')
  })

  it('checks the travellers and the dates against the offers once they are all set', async () => {
    renderPreferences()
    await openPanel()

    fill(SUMMER)

    await waitFor(() => expect(fitReads()).toHaveLength(1))
    const search = fitReads()[0]!.search
    expect(search.get('persons')).toBe('2')
    expect(search.get('start_date')).toBe('2027-05-12')
    expect(search.get('end_date')).toBe('2027-05-19')
  })

  it('does not check dates in the wrong order', async () => {
    renderPreferences()
    await openPanel()

    fill({ start: '2027-05-19', end: '2027-05-12' })
    fireEvent.change(screen.getByLabelText('Return'), { target: { value: '2027-05-26' } })

    await waitFor(() => expect(fitReads()).toHaveLength(1))
    expect(fitReads()[0]!.search.get('start_date')).toBe('2027-05-19')
    expect(fitReads()[0]!.search.get('end_date')).toBe('2027-05-26')
  })

  it('says no offer fits before sending, sends nothing, and lets the client change the dates', async () => {
    renderPreferences()
    await openPanel()
    fill(WINTER)

    const message = await screen.findByText(/No offer in Chania/)
    expect(message).toHaveTextContent(
      /^No offer in Chania for 2 travellers on these dates\. Offers are open in May, June,? and July\.$/,
    )

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))
    await act(async () => {})
    expect(answerPosts()).toHaveLength(0)
    expect(screen.getByText(/No offer in Chania/)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Departure'), { target: { value: SUMMER.start } })
    fireEvent.change(screen.getByLabelText('Return'), { target: { value: SUMMER.end } })
    await waitFor(() => expect(screen.queryByText(/No offer in Chania/)).not.toBeInTheDocument())
    await waitFor(() => expect(fitReads().some((call) => call.search.get('start_date') === SUMMER.start)).toBe(true))

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))
    await waitFor(() => expect(answerPosts()).toHaveLength(1))
    expect(answerPosts()[0]!.body).toMatchObject({ persons: 2, start_date: SUMMER.start, end_date: SUMMER.end })
  })

  it('counts a single traveller in the singular', async () => {
    renderPreferences()
    await openPanel()
    fireEvent.click(screen.getByRole('button', { name: 'One traveller fewer' }))
    fill(WINTER)

    expect(await screen.findByText(/No offer in Chania/)).toHaveTextContent(/^No offer in Chania for 1 traveller on these dates\./)
  })

  it('names the country when the destination has no city', async () => {
    renderPreferences({ ...PANEL_WISH, destination: { country: 'Greece', city: null } })
    await openPanel()
    fill(WINTER)

    expect(await screen.findByText(/No offer in Greece/)).toHaveTextContent(/^No offer in Greece for 2 travellers on these dates\./)
  })

  it('says only the first sentence when no month is open', async () => {
    limits = { ...LIMITS, open_months: [] }
    renderPreferences()
    await openPanel()
    fill(WINTER)

    expect(await screen.findByText(/No offer in Chania/)).toHaveTextContent(
      /^No offer in Chania for 2 travellers on these dates\.$/,
    )
    expect(screen.queryByText(/Offers are open/)).not.toBeInTheDocument()
  })

  it('links the message to the departure so screen readers read it with the date', async () => {
    renderPreferences()
    await openPanel()
    fill(WINTER)

    const message = await screen.findByText(/No offer in Chania/)

    // Field links its error to the control with aria-describedby (hint and error ids): the
    // message is expected to reach the departure input the same way, so its own id is needed.
    expect(message.id).not.toBe('')
    const describedBy = screen.getByLabelText('Departure').getAttribute('aria-describedby') ?? ''
    expect(describedBy.split(' ')).toContain(message.id)
  })

  it('says no offer fits in French, with the month names in French', async () => {
    signedIn = { ...CAMILLE, locale: 'fr' }
    renderPreferences()
    await screen.findByRole('heading', { name: /Ce qui compte/ })
    await waitFor(() => expect(plainLimitsReads()).toHaveLength(1))
    fireEvent.change(screen.getByLabelText(/Budget maximum/), { target: { value: '3 500 €' } })
    fireEvent.change(screen.getByLabelText('Départ'), { target: { value: WINTER.start } })
    fireEvent.change(screen.getByLabelText('Retour'), { target: { value: WINTER.end } })

    expect(await screen.findByText(/Aucune offre à Chania/)).toHaveTextContent(
      /^Aucune offre à Chania pour 2 voyageurs à ces dates\. Les offres sont ouvertes en mai, juin et juillet\.$/,
    )
  })

  it('says a single traveller in the singular in French', async () => {
    signedIn = { ...CAMILLE, locale: 'fr' }
    renderPreferences()
    await screen.findByRole('heading', { name: /Ce qui compte/ })
    await waitFor(() => expect(plainLimitsReads()).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: 'Un voyageur de moins' }))
    fireEvent.change(screen.getByLabelText(/Budget maximum/), { target: { value: '3 500 €' } })
    fireEvent.change(screen.getByLabelText('Départ'), { target: { value: WINTER.start } })
    fireEvent.change(screen.getByLabelText('Retour'), { target: { value: WINTER.end } })

    expect(await screen.findByText(/Aucune offre à Chania/)).toHaveTextContent(/^Aucune offre à Chania pour 1 voyageur à ces dates\./)
  })

  it('does not hold the sending while the offers are still being checked', async () => {
    fitAnswer = () => new Promise<Response>(() => {})
    renderPreferences()
    await openPanel()
    fill(SUMMER)
    await waitFor(() => expect(fitReads()).toHaveLength(1))

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    await waitFor(() => expect(answerPosts()).toHaveLength(1))
  })

  it('does not hold the sending when the offers cannot be checked', async () => {
    fitAnswer = () => Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
    renderPreferences()
    await openPanel()
    fill(WINTER)
    await waitFor(() => expect(fitReads()).toHaveLength(1))

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    await waitFor(() => expect(answerPosts()).toHaveLength(1))
    expect(screen.queryByText(/No offer in Chania/)).not.toBeInTheDocument()
  })

  // Review of #183

  it("never offers more than the panel's fifty travellers, whatever the offers take", async () => {
    limits = { ...LIMITS, persons_min: 48, persons_max: 200 }
    renderPreferences()
    await openPanel()

    const more = screen.getByRole('button', { name: 'One more traveller' })
    await waitFor(() => expect(screen.getByText('48 travellers')).toBeInTheDocument())
    fireEvent.click(more)
    fireEvent.click(more)
    fireEvent.click(more)

    expect(screen.getByText('50 travellers')).toBeInTheDocument()
    expect(more).toHaveAttribute('aria-disabled', 'true')
  })

  it("sends the travellers the stepper shows, raised to the offers' smallest group", async () => {
    limits = { ...LIMITS, persons_min: 4 }
    renderPreferences()
    await openPanel()
    await waitFor(() => expect(screen.getByText('4 travellers')).toBeInTheDocument())
    fill(SUMMER)
    await waitFor(() => expect(fitReads().length).toBeGreaterThan(0))

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    await waitFor(() => expect(answerPosts()).toHaveLength(1))
    expect(answerPosts()[0]!.body).toMatchObject({ persons: 4 })
  })

  it('sets no last date when the offers end before today on the client side', async () => {
    // The server allows one day back (its day is UTC): its last date can be yesterday here.
    limits = { ...LIMITS, first_date: '2026-10-22', last_date: '2026-10-22' }
    renderPreferences()
    await openPanel()

    await waitFor(() => expect(screen.getByLabelText('Departure')).toHaveAttribute('min', TODAY))
    expect(screen.getByLabelText('Departure')).not.toHaveAttribute('max')
    expect(screen.getByLabelText('Return')).not.toHaveAttribute('max')
  })

  it('names no months when the trip is already in open months', async () => {
    // The group or the nights are the reason here, not the season: the months would mislead.
    fitAnswer = () => Response.json({ ...limits, open_months: [1, 2], fits: false })
    renderPreferences()
    await openPanel()
    fill(WINTER)

    expect(await screen.findByText(/No offer in Chania/)).toHaveTextContent(
      /^No offer in Chania for 2 travellers on these dates\.$/,
    )
  })

  it('names the months the offers taking this group are open', async () => {
    fitAnswer = () => Response.json({ ...limits, open_months: [8], fits: false })
    renderPreferences()
    await openPanel()
    fill(WINTER)

    expect(await screen.findByText(/No offer in Chania/)).toHaveTextContent(/Offers are open in August\.$/)
  })

  it('announces the message and moves to it when sending is held', async () => {
    renderPreferences()
    await openPanel()
    fill(WINTER)
    const message = await screen.findByText(/No offer in Chania/)
    expect(message).toHaveAttribute('aria-live', 'polite')

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    await waitFor(() => expect(message).toHaveFocus())
  })

  it('links the message to the travellers too, since they can be the reason', async () => {
    renderPreferences()
    await openPanel()
    fill(WINTER)
    const message = await screen.findByText(/No offer in Chania/)

    const stepper = screen.getByRole('button', { name: 'One more traveller' })
    const described = [stepper, ...screen.getAllByText('2 travellers')]
      .map((element) => element.closest('[aria-describedby]')?.getAttribute('aria-describedby') ?? '')
      .join(' ')
    expect(described.split(' ')).toContain(message.id)
  })


  it('offers the closest dates that fit, and builds the plan for them when picked (#184)', async () => {
    const { router } = renderPreferences()
    await openPanel()
    fill(WINTER)
    await screen.findByText(/No offer in Chania/)

    const pick = await screen.findByRole('button', { name: /May 1.+8, 2027 · 3 offers fit/ })
    const closest = calls.find((call) => call.path === CLOSEST_PATH)!
    expect(Object.fromEntries(closest.search)).toEqual({ persons: '2', start_date: WINTER.start, end_date: WINTER.end })

    fireEvent.click(pick)
    await waitFor(() => expect(answerPosts()).toHaveLength(1))
    expect(answerPosts()[0]!.body).toMatchObject({ persons: 2, start_date: '2027-05-01', end_date: '2027-05-08' })
    await waitFor(() => expect(router.state.location.pathname).toBe(`/plans/${PLAN.id}`))
  })

  it('sends the trip to the agency anyway, with the answers as they are (#184)', async () => {
    const { router } = renderPreferences()
    await openPanel()
    fill(WINTER)
    await screen.findByText(/No offer in Chania/)

    fireEvent.click(await screen.findByRole('button', { name: 'Send to the agency anyway' }))

    await waitFor(() => expect(customPosts()).toHaveLength(1))
    expect(customPosts()[0]!.body).toMatchObject({
      persons: 2,
      start_date: WINTER.start,
      end_date: WINTER.end,
      currency: 'EUR',
      selected_tags: [{ section: 'mood', tag: 'calm' }],
    })
    expect(answerPosts()).toHaveLength(0)
    await waitFor(() => expect(router.state.location.pathname).toBe(`/plans/${CUSTOM_PLAN_ID}`))
  })

  it('shows no way out while the trip fits', async () => {
    renderPreferences()
    await openPanel()
    fill(SUMMER)
    await waitFor(() => expect(fitReads().some((call) => call.search.get('start_date') === SUMMER.start)).toBe(true))

    expect(screen.queryByRole('button', { name: 'Send to the agency anyway' })).not.toBeInTheDocument()
    expect(calls.some((call) => call.path === CLOSEST_PATH)).toBe(false)
  })
})
