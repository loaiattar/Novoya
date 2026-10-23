import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { getPlanQuoteQueryKey } from '../api/generated/@tanstack/react-query.gen'
import { client } from '../api/generated/client.gen'
import type { AgentPlan, AgentPlanExtra, AgentPlanItem, MeResponse, PlanQuote, Quote } from '../api/generated/types.gen'
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

const PLAN_ID = '00000000-0000-4000-8000-000000000020'

const HOTEL: AgentPlanItem = {
  id: '00000000-0000-4000-8000-000000000031',
  offer_id: '00000000-0000-4000-8000-000000000041',
  day: 1,
  quantity: 1,
  note: null,
  kind: 'hotel',
  title: 'Maison face au port',
  description: 'Chambres sur la baie.',
  available: true,
  negotiated_price: '1200.00',
  removed: false,
  partner_name: 'Maison du Port',
  partner_contact_email: 'contact@maison-port.example',
  partner_contact_phone: '+30 282 100 0000',
}

const WALK: AgentPlanItem = {
  ...HOTEL,
  id: '00000000-0000-4000-8000-000000000032',
  offer_id: '00000000-0000-4000-8000-000000000042',
  day: 2,
  kind: 'guide',
  title: 'Chania à pied',
  description: null,
  negotiated_price: null,
  partner_name: 'Kriti Walks',
  partner_contact_email: 'hello@kriti-walks.example',
  partner_contact_phone: '+30 282 100 0001',
}

const TRANSFER: AgentPlanExtra = {
  extra_id: '00000000-0000-4000-8000-000000000051',
  label: 'Airport transfer',
  pricing: 'on_quote',
  unit: 'trip',
  price_eur: null,
  needs_quantity_check: false,
  confirmed: false,
}

// Two lines still without a price: not ready.
const NOT_READY: AgentPlan = {
  id: PLAN_ID,
  wish_id: '00000000-0000-4000-8000-000000000010',
  status: 'negotiating',
  summary: 'Une semaine calme entre mer et vieille ville.',
  items: [WALK, HOTEL],
  extras: [TRANSFER],
  total: '1200.00',
  ready_to_quote: false,
  budget_max: '3000.00',
  currency: 'EUR',
  over_budget: false,
  assigned_agent_id: AGENT.id,
  wish_text: 'De bonnes tables et beaucoup de mer.',
  country: 'Greece',
  city: 'Chania',
  persons: 2,
  start_date: '2027-05-12',
  end_date: '2027-05-19',
}

const READY: AgentPlan = {
  ...NOT_READY,
  items: [{ ...WALK, negotiated_price: '450.00' }, HOTEL],
  extras: [{ ...TRANSFER, price_eur: '60.00' }],
  total: '1710.00',
  ready_to_quote: true,
}

const QUOTE: Quote = {
  id: '00000000-0000-4000-8000-000000000061',
  number: 'NV-2026-0042',
  plan_id: PLAN_ID,
  total: '1710.00',
  currency: 'EUR',
  locale: 'en',
  sent_at: '2026-10-22T10:00:00Z',
  valid_until: '2026-10-29',
  email_sent: true,
}

// What GET /agent/plans/{id}/quote answers: the sent quote and where it stands.
const { email_sent: _emailSent, ...QUOTE_FIELDS } = QUOTE
const OPEN_QUOTE: PlanQuote = { ...QUOTE_FIELDS, status: 'open', decided_at: null, client_comment: null }

type Answer = (body: unknown) => Response | Promise<Response>

let me: MeResponse
let plan: AgentPlan
let planAnswer: () => Response
let itemAnswer: Answer
let extraAnswer: Answer
let quoteAnswer: () => Response | Promise<Response>
let planQuote: PlanQuote
let requests: { method: string; path: string; search: string; body?: unknown }[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    const body = request.method === 'GET' ? undefined : await request.clone().json().catch(() => undefined)
    requests.push({ method: request.method, path: url.pathname, search: url.search, body })
    if (url.pathname === '/me') return Response.json(me)
    if (url.pathname === `/agent/plans/${PLAN_ID}` && request.method === 'GET') return planAnswer()
    if (url.pathname.startsWith(`/agent/plans/${PLAN_ID}/items/`) && request.method === 'PATCH') return itemAnswer(body)
    if (url.pathname.startsWith(`/agent/plans/${PLAN_ID}/extras/`) && request.method === 'PATCH') return extraAnswer(body)
    if (url.pathname === `/agent/plans/${PLAN_ID}/quote` && request.method === 'POST') return quoteAnswer()
    if (url.pathname === `/agent/plans/${PLAN_ID}/quote` && request.method === 'GET') {
      return ['quoted', 'accepted', 'rejected'].includes(plan.status)
        ? Response.json(planQuote)
        : Response.json({ code: 'not_found', detail: 'no quote' }, { status: 404 })
    }
    return Response.json({ code: 'not_found', detail: 'no route' }, { status: 404 })
  })
}

const sent = (method: string, path: string) => requests.filter((request) => request.method === method && request.path === path)
const planReads = () => sent('GET', `/agent/plans/${PLAN_ID}`).length
const priceOf = (title: string) => screen.getByLabelText(`Price of ${title}`) as HTMLInputElement
const enterPrice = (title: string, value: string) => {
  const input = priceOf(title)
  fireEvent.change(input, { target: { value } })
  fireEvent.blur(input)
}

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

describe('agent plan page', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    me = AGENT
    plan = NOT_READY
    planAnswer = () => Response.json(plan)
    itemAnswer = () => Response.json(plan)
    extraAnswer = () => Response.json(plan)
    quoteAnswer = () => {
      plan = { ...plan, status: 'quoted' }
      return Response.json(QUOTE, { status: 201 })
    }
    planQuote = OPEN_QUOTE
    requests = []
    mockApi()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('shows the items day by day, with the partner to call or write to', async () => {
    renderAt(`/agent/plans/${PLAN_ID}`)

    expect(await screen.findByText(NOT_READY.summary)).toBeInTheDocument()
    const days = screen.getAllByRole('heading', { level: 2, name: /^Day / }).map((heading) => heading.textContent)
    expect(days).toEqual(['Day 1', 'Day 2'])
    expect(screen.getByRole('heading', { name: 'Maison face au port' })).toBeInTheDocument()
    expect(screen.getByText('Maison du Port')).toBeInTheDocument()
    expect(screen.getByText('+30 282 100 0000')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'contact@maison-port.example' })).toHaveAttribute(
      'href',
      'mailto:contact@maison-port.example',
    )
  })

  it('saves an item price on blur and shows the new total', async () => {
    itemAnswer = () => Response.json({ ...NOT_READY, items: [{ ...WALK, negotiated_price: '450.00' }, HOTEL], total: '1650.00' })
    renderAt(`/agent/plans/${PLAN_ID}`)
    await screen.findByLabelText('Price of Chania à pied')

    enterPrice('Chania à pied', '450')

    await waitFor(() => expect(sent('PATCH', `/agent/plans/${PLAN_ID}/items/${WALK.id}`)).toHaveLength(1))
    const [patch] = sent('PATCH', `/agent/plans/${PLAN_ID}/items/${WALK.id}`)
    expect(Object.keys(patch.body as object)).toEqual(['negotiated_price'])
    expect(Number((patch.body as { negotiated_price: unknown }).negotiated_price)).toBe(450)
    expect(await screen.findByText('€1,650')).toBeInTheDocument()
  })

  it('removes an item, then puts it back', async () => {
    itemAnswer = (body) =>
      Response.json({
        ...NOT_READY,
        items: [{ ...WALK, removed: (body as { removed: boolean }).removed }, HOTEL],
      })
    renderAt(`/agent/plans/${PLAN_ID}`)

    fireEvent.click(await screen.findByRole('button', { name: 'Remove Chania à pied' }))
    await waitFor(() =>
      expect(requests).toContainEqual(
        expect.objectContaining({ method: 'PATCH', path: `/agent/plans/${PLAN_ID}/items/${WALK.id}`, body: { removed: true } }),
      ),
    )
    fireEvent.click(await screen.findByRole('button', { name: 'Put back Chania à pied' }))

    await waitFor(() =>
      expect(requests).toContainEqual(
        expect.objectContaining({ method: 'PATCH', path: `/agent/plans/${PLAN_ID}/items/${WALK.id}`, body: { removed: false } }),
      ),
    )
    expect(await screen.findByRole('button', { name: 'Remove Chania à pied' })).toBeInTheDocument()
  })

  it('says by the line when a price was not saved, and keeps what was typed', async () => {
    itemAnswer = () => Response.json({ code: 'invalid_input', detail: 'negotiated_price: must be positive' }, { status: 422 })
    renderAt(`/agent/plans/${PLAN_ID}`)
    await screen.findByLabelText('Price of Chania à pied')

    enterPrice('Chania à pied', '-5')

    await waitFor(() => expect(priceOf('Chania à pied')).toHaveAccessibleDescription('This price was not saved. Check the amount.'))
    expect(priceOf('Chania à pied')).toHaveValue('-5')
  })

  it('saves the price of an on_quote extra', async () => {
    renderAt(`/agent/plans/${PLAN_ID}`)
    await screen.findByLabelText('Price of Airport transfer')

    enterPrice('Airport transfer', '60')

    await waitFor(() => expect(sent('PATCH', `/agent/plans/${PLAN_ID}/extras/${TRANSFER.extra_id}`)).toHaveLength(1))
    const [patch] = sent('PATCH', `/agent/plans/${PLAN_ID}/extras/${TRANSFER.extra_id}`)
    expect(Object.keys(patch.body as object)).toEqual(['price_eur'])
    expect(Number((patch.body as { price_eur: unknown }).price_eur)).toBe(60)
  })

  it('confirms a supplement at the price it already has, once the quantity is checked', async () => {
    const lateCheckout: AgentPlanExtra = {
      ...TRANSFER,
      extra_id: '00000000-0000-4000-8000-000000000052',
      label: 'Late check-out',
      pricing: 'supplement',
      unit: 'night',
      price_eur: '20.00',
      needs_quantity_check: true,
    }
    plan = { ...NOT_READY, extras: [TRANSFER, lateCheckout] }
    renderAt(`/agent/plans/${PLAN_ID}`)

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm Late check-out' }))

    await waitFor(() =>
      expect(requests).toContainEqual(
        expect.objectContaining({
          method: 'PATCH',
          path: `/agent/plans/${PLAN_ID}/extras/${lateCheckout.extra_id}`,
          body: { price_eur: '20.00' },
        }),
      ),
    )
  })

  it('sends a price once when Enter is followed by leaving the field', async () => {
    renderAt(`/agent/plans/${PLAN_ID}`)
    const input = await screen.findByLabelText('Price of Chania à pied')

    fireEvent.change(input, { target: { value: '450' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    fireEvent.blur(input)

    await waitFor(() => expect(sent('PATCH', `/agent/plans/${PLAN_ID}/items/${WALK.id}`)).toHaveLength(1))
  })

  it('shows the saved price again when the field is emptied', async () => {
    renderAt(`/agent/plans/${PLAN_ID}`)
    await screen.findByLabelText('Price of Maison face au port')

    enterPrice('Maison face au port', '')

    expect(priceOf('Maison face au port')).toHaveValue('1200')
    expect(sent('PATCH', `/agent/plans/${PLAN_ID}/items/${HOTEL.id}`)).toHaveLength(0)
  })

  it('shows the total next to the budget', async () => {
    renderAt(`/agent/plans/${PLAN_ID}`)

    await screen.findByText(NOT_READY.summary)
    expect(document.body).toHaveTextContent('€1,200')
    expect(document.body).toHaveTextContent('€3,000')
    expect(screen.queryByText("The total is over the client's budget.")).not.toBeInTheDocument()
  })

  it('warns when the total is over the budget', async () => {
    plan = { ...READY, budget_max: '1500.00', over_budget: true }
    renderAt(`/agent/plans/${PLAN_ID}`)

    expect(await screen.findByText("The total is over the client's budget.")).toBeInTheDocument()
  })

  it('cannot send the quote while lines have no price, and lists them', async () => {
    renderAt(`/agent/plans/${PLAN_ID}`)

    expect(await screen.findByRole('button', { name: 'Send the quote' })).toBeDisabled()
    const missing = screen.getByRole('list', { name: 'Still to price' })
    expect(within(missing).getAllByRole('listitem').map((line) => line.textContent)).toEqual([
      'Day 2 · Chania à pied',
      'Airport transfer',
    ])
  })

  describe('sending the quote', () => {
    beforeEach(() => {
      vi.useFakeTimers({ toFake: ['Date'] })
      vi.setSystemTime(new Date('2026-10-22T10:00:00Z'))
      plan = READY
    })

    it('asks first, with the total, the budget and the validity date', async () => {
      renderAt(`/agent/plans/${PLAN_ID}`)

      fireEvent.click(await screen.findByRole('button', { name: 'Send the quote' }))

      const dialog = await screen.findByRole('alertdialog', { name: 'Send the quote?' })
      expect(dialog).toHaveTextContent('€1,710')
      expect(dialog).toHaveTextContent('€3,000')
      expect(dialog).toHaveTextContent(/Valid until (29 October 2026|October 29, 2026)/)
    })

    it("shows the validity as the agency's day in Paris, like the PDF", async () => {
      // 23:30 UTC on 22 October is already 23 October in Paris: valid until 30 October.
      vi.setSystemTime(new Date('2026-10-22T23:30:00Z'))
      renderAt(`/agent/plans/${PLAN_ID}`)

      fireEvent.click(await screen.findByRole('button', { name: 'Send the quote' }))

      const dialog = await screen.findByRole('alertdialog', { name: 'Send the quote?' })
      expect(dialog).toHaveTextContent('Valid until October 30, 2026')
    })

    it('says in the dialog when the client gave no budget', async () => {
      plan = { ...READY, budget_max: null }
      renderAt(`/agent/plans/${PLAN_ID}`)

      fireEvent.click(await screen.findByRole('button', { name: 'Send the quote' }))

      expect(await screen.findByRole('alertdialog', { name: 'Send the quote?' })).toHaveTextContent('No budget given')
    })

    it('sends nothing when the agent cancels', async () => {
      renderAt(`/agent/plans/${PLAN_ID}`)
      fireEvent.click(await screen.findByRole('button', { name: 'Send the quote' }))
      const dialog = await screen.findByRole('alertdialog', { name: 'Send the quote?' })

      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))

      await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
      expect(sent('POST', `/agent/plans/${PLAN_ID}/quote`)).toHaveLength(0)
    })

    it('sends one POST without a locale, even on a double click', async () => {
      let finish!: () => void
      const answer = quoteAnswer
      quoteAnswer = () => new Promise((resolve) => (finish = () => resolve(answer())))
      renderAt(`/agent/plans/${PLAN_ID}`)
      fireEvent.click(await screen.findByRole('button', { name: 'Send the quote' }))
      const confirm = within(await screen.findByRole('alertdialog', { name: 'Send the quote?' })).getByRole('button', {
        name: 'Send',
      })

      fireEvent.click(confirm)
      fireEvent.click(confirm)
      await waitFor(() => expect(finish).toBeDefined())
      finish()

      expect(await screen.findByText('NV-2026-0042')).toBeInTheDocument()
      const posts = sent('POST', `/agent/plans/${PLAN_ID}/quote`)
      expect(posts).toHaveLength(1)
      expect(posts[0].body ?? {}).not.toHaveProperty('locale')
    })

    it('shows the quote as sent, with its number and its PDF', async () => {
      const { queryClient } = renderAt(`/agent/plans/${PLAN_ID}`)
      fireEvent.click(await screen.findByRole('button', { name: 'Send the quote' }))
      const dialog = await screen.findByRole('alertdialog', { name: 'Send the quote?' })

      fireEvent.click(within(dialog).getByRole('button', { name: 'Send' }))

      expect(await screen.findByText('NV-2026-0042')).toBeInTheDocument()
      expect(screen.getByText('Quoted')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Download the quote (PDF)' })).toHaveAttribute(
        'href',
        `http://api.test/quotes/${QUOTE.id}/pdf`,
      )
      expect(screen.queryByRole('button', { name: 'Send the quote' })).not.toBeInTheDocument()
      expect(screen.getByText("Waiting for the client's answer.")).toBeInTheDocument()
      // The page reads the quote from what sending answered: open, no answer, no email_sent.
      const cached = queryClient.getQueryData(getPlanQuoteQueryKey({ path: { plan_id: PLAN_ID } }))
      expect(cached).toMatchObject({ status: 'open', decided_at: null, client_comment: null })
      expect(cached).not.toHaveProperty('email_sent')
    })

    it('shows the answer once the client gives it while the page is open', async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'], shouldAdvanceTime: true })
      plan = { ...READY, status: 'quoted' }
      renderAt(`/agent/plans/${PLAN_ID}`)
      expect(await screen.findByText("Waiting for the client's answer.")).toBeInTheDocument()

      plan = { ...READY, status: 'rejected' }
      planQuote = { ...OPEN_QUOTE, status: 'rejected', decided_at: '2026-10-24T08:30:00Z', client_comment: 'Too far' }
      const before = planReads()
      // No focus, no reload: the open quote is read again every minute.
      await vi.advanceTimersByTimeAsync(60_000)

      expect(await screen.findByText('The client declined the quote on October 24, 2026.')).toBeInTheDocument()
      expect(screen.getByText('Too far')).toBeInTheDocument()
      // The plan follows the answer: read again, its status is now declined.
      await waitFor(() => expect(planReads()).toBeGreaterThan(before))
      expect(await screen.findByText('Declined')).toBeInTheDocument()
    })

    it('stops reading the quote again once the client answered', async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'], shouldAdvanceTime: true })
      plan = { ...READY, status: 'accepted' }
      planQuote = { ...OPEN_QUOTE, status: 'accepted', decided_at: '2026-10-24T08:30:00Z' }
      renderAt(`/agent/plans/${PLAN_ID}`)
      await screen.findByText('The client accepted the quote on October 24, 2026.')
      const reads = sent('GET', `/agent/plans/${PLAN_ID}/quote`).length

      await vi.advanceTimersByTimeAsync(5 * 60_000)

      expect(sent('GET', `/agent/plans/${PLAN_ID}/quote`)).toHaveLength(reads)
    })

    it("shows the client's answer and comment", async () => {
      plan = { ...READY, status: 'accepted' }
      planQuote = { ...OPEN_QUOTE, status: 'accepted', decided_at: '2026-10-24T08:30:00Z', client_comment: 'See you in May!' }
      renderAt(`/agent/plans/${PLAN_ID}`)

      expect(await screen.findByText('The client accepted the quote on October 24, 2026.')).toBeInTheDocument()
      expect(screen.getByText('See you in May!')).toBeInTheDocument()
    })

    it('says when the client declined without a comment', async () => {
      plan = { ...READY, status: 'rejected' }
      planQuote = { ...OPEN_QUOTE, status: 'rejected', decided_at: '2026-10-24T08:30:00Z' }
      renderAt(`/agent/plans/${PLAN_ID}`)

      expect(await screen.findByText('The client declined the quote on October 24, 2026.')).toBeInTheDocument()
      expect(screen.getByRole('status')).toHaveTextContent("Client's comment: none.")
    })

    it('says when the quote expired without an answer', async () => {
      plan = { ...READY, status: 'quoted' }
      planQuote = { ...OPEN_QUOTE, status: 'expired' }
      renderAt(`/agent/plans/${PLAN_ID}`)

      expect(await screen.findByText('The quote expired on October 29, 2026 without an answer.')).toBeInTheDocument()
    })

    it('explains when the plan is not ready after all, reads it again and keeps the prices', async () => {
      quoteAnswer = () => Response.json({ code: 'plan_not_ready', detail: 'a line has no price' }, { status: 422 })
      renderAt(`/agent/plans/${PLAN_ID}`)
      fireEvent.click(await screen.findByRole('button', { name: 'Send the quote' }))
      const readsBefore = planReads()

      fireEvent.click(within(await screen.findByRole('alertdialog', { name: 'Send the quote?' })).getByRole('button', { name: 'Send' }))

      expect(
        await screen.findByText('Some lines still have no price. The plan was read again: check it and try once more.'),
      ).toBeInTheDocument()
      await waitFor(() => expect(planReads()).toBeGreaterThan(readsBefore))
      expect(Number(priceOf('Chania à pied').value)).toBe(450)
      expect(Number(priceOf('Maison face au port').value)).toBe(1200)
      expect(Number(priceOf('Airport transfer').value)).toBe(60)
    })

    it('says when the quote was already sent or the plan is no longer negotiated', async () => {
      quoteAnswer = () => Response.json({ code: 'invalid_transition', detail: 'not negotiating' }, { status: 409 })
      renderAt(`/agent/plans/${PLAN_ID}`)
      fireEvent.click(await screen.findByRole('button', { name: 'Send the quote' }))

      fireEvent.click(within(await screen.findByRole('alertdialog', { name: 'Send the quote?' })).getByRole('button', { name: 'Send' }))

      expect(
        await screen.findByText('This quote was already sent, or the plan is no longer being negotiated.'),
      ).toBeInTheDocument()
    })
  })

  it('reads the quote of a plan already quoted and links its PDF', async () => {
    plan = { ...READY, status: 'quoted' }
    renderAt(`/agent/plans/${PLAN_ID}`)

    expect(await screen.findByRole('link', { name: 'Download the quote (PDF)' })).toHaveAttribute(
      'href',
      `http://api.test/quotes/${QUOTE.id}/pdf`,
    )
    expect(sent('GET', `/agent/plans/${PLAN_ID}/quote`)).toHaveLength(1)
    expect(screen.getByText('NV-2026-0042')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send the quote' })).not.toBeInTheDocument()
  })

  it('says when the quote of a quoted plan cannot be read, with a way to try again', async () => {
    plan = { ...READY, status: 'quoted' }
    const answer = planAnswer
    let quoteReads = 0
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const request = input instanceof Request ? input : new Request(String(input))
      const url = new URL(request.url)
      if (url.pathname === `/agent/plans/${PLAN_ID}/quote`) {
        quoteReads += 1
        return quoteReads === 1 ? Response.json({ code: 'internal', detail: 'boom' }, { status: 500 }) : Response.json(QUOTE)
      }
      if (url.pathname === '/me') return Response.json(me)
      return answer()
    })
    renderAt(`/agent/plans/${PLAN_ID}`)

    expect(await screen.findByText("We couldn't load the quote.")).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('link', { name: 'Download the quote (PDF)' })).toBeInTheDocument()
  })

  it("shows the plan in the agent's language", async () => {
    me = { ...AGENT, locale: 'fr' }
    plan = READY
    renderAt(`/agent/plans/${PLAN_ID}`)

    expect(await screen.findByRole('button', { name: 'Envoyer le devis' })).toBeInTheDocument()
  })

  it("says the plan does not exist when it is another agent's", async () => {
    planAnswer = () => Response.json({ code: 'forbidden', detail: 'not your plan' }, { status: 403 })
    renderAt(`/agent/plans/${PLAN_ID}`)

    expect(await screen.findByText("This plan doesn't exist or isn't yours.")).toBeInTheDocument()
  })

  it('sends a client away', async () => {
    me = { ...AGENT, role: 'client' }
    const { router } = renderAt(`/agent/plans/${PLAN_ID}`)

    await waitFor(() => expect(router.state.location.pathname).toBe('/wish'))
  })
})
