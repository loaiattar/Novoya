import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse, PlanResponse, WishResponse } from '../api/generated/types.gen'
import { type CachedWish, wishQueryKey } from '../api/wishes'
import { createAppRouter } from '../router'

const CAMILLE: MeResponse = {
  id: '6f1c2b1e-0000-4000-8000-000000000002',
  email: 'camille@exemple.fr',
  name: 'Camille Martin',
  first_name: 'Camille',
  last_name: 'Martin',
  role: 'client',
  locale: 'en',
  status: 'active',
  status_changed_by: null,
  status_changed_at: null,
  email_verified: true,
  created_at: '2026-10-01T10:00:00Z',
  sign_in_methods: ['password'],
}

const WISH_ID = '0b5f8a52-0000-4000-8000-000000000010'

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
        tags: [
          { id: 'calm', label: 'Calme', preselected: true },
          { id: 'culture', label: 'Culture', preselected: false },
        ],
      },
      {
        id: 'pace',
        title: 'Rythme',
        multi: false,
        tags: [
          { id: 'slow', label: 'Très doux', preselected: false },
          { id: 'busy', label: 'Dynamique', preselected: false },
        ],
      },
    ],
  },
}

const PLAN_ID = '0b5f8a52-0000-4000-8000-000000000020'

const PLAN: PlanResponse = {
  id: PLAN_ID,
  wish_id: WISH_ID,
  status: 'proposed',
  based_on_preferences: true,
  summary: 'Une semaine calme à Chania',
  items: [],
}

const NOT_COVERED: WishResponse = {
  id: '0b5f8a52-0000-4000-8000-000000000011',
  status: 'not_covered',
  destination: { country: 'Japan', city: 'Kyoto' },
  suggestions: [
    { country: 'Greece', city: 'Chania' },
    { country: 'Morocco', city: 'Marrakech' },
  ],
  panel: null,
}

type Call = { method: string; path: string; body: unknown }

let signedIn: MeResponse | null
let calls: Call[]
let wishAnswer: () => Response
let loginAnswer: () => Response
let answersAnswer: () => Response | Promise<Response>

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    const text = request.method === 'POST' ? await request.text() : ''
    calls.push({ method: request.method, path, body: text ? JSON.parse(text) : undefined })
    if (path === '/me') {
      return signedIn
        ? Response.json(signedIn)
        : Response.json({ code: 'unauthenticated', detail: 'not signed in' }, { status: 401 })
    }
    if (path === '/auth/login') return loginAnswer()
    if (path === '/wishes') return wishAnswer()
    if (path === `/wishes/${WISH_ID}/answers`) return answersAnswer()
    return Response.json({ status: 'ok' })
  })
}

function renderAt(url: string, prepare?: (queryClient: QueryClient) => void) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  prepare?.(queryClient)
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [url] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, queryClient }
}

const posts = (path: string) => calls.filter((call) => call.method === 'POST' && call.path === path)

beforeEach(() => {
  client.setConfig({ baseUrl: 'http://api.test' })
  signedIn = CAMILLE
  calls = []
  wishAnswer = () => Response.json(PANEL_WISH, { status: 201 })
  loginAnswer = () => new Response(null, { status: 204 })
  answersAnswer = () => Response.json(PLAN, { status: 201 })
  mockApi()
})
afterEach(() => {
  vi.restoreAllMocks()
})

describe('signing in with an e-mail and a password', () => {
  async function fillAndSend(password: string) {
    fireEvent.change(await screen.findByLabelText('E-mail'), { target: { value: ' camille@exemple.fr ' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } })
    fireEvent.click(screen.getByRole('button', { name: /^Sign in/ }))
  }

  it('signs in and goes to the requested page', async () => {
    signedIn = null
    loginAnswer = () => {
      signedIn = CAMILLE
      return new Response(null, { status: 204 })
    }
    const { router } = renderAt('/login?redirect=%2Fwish%3Ffrom%3Dlogin')

    await fillAndSend('correct horse')

    expect(await screen.findByRole('heading', { name: /What would you/ })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/wish')
    expect(posts('/auth/login')[0]!.body).toEqual({ email: 'camille@exemple.fr', password: 'correct horse' })
  })

  it('says so when the password is wrong, and stays on the page', async () => {
    signedIn = null
    loginAnswer = () => Response.json({ code: 'invalid_credentials', detail: 'nope' }, { status: 401 })
    const { router } = renderAt('/login')

    await fillAndSend('wrong')

    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong e-mail or password.')
    expect(router.state.location.pathname).toBe('/login')
  })

  it('asks to confirm the e-mail first when it is not verified', async () => {
    signedIn = null
    loginAnswer = () => Response.json({ code: 'email_not_verified', detail: 'verify' }, { status: 403 })
    renderAt('/login')

    await fillAndSend('correct horse')

    expect(await screen.findByRole('alert')).toHaveTextContent('Please confirm your e-mail address first')
  })
})

describe('sending a wish', () => {
  async function writeAndSend(text: string) {
    fireEvent.change(await screen.findByLabelText('Your travel wish'), { target: { value: text } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  }

  it('greets the client by first name', async () => {
    renderAt('/wish')
    expect(await screen.findByText('Hello Camille')).toBeInTheDocument()
  })

  it('greets with the first word of name when first_name is missing', async () => {
    signedIn = { ...CAMILLE, first_name: null }
    renderAt('/wish')
    expect(await screen.findByText('Hello Camille')).toBeInTheDocument()
  })

  it("speaks French to a client whose locale is French", async () => {
    signedIn = { ...CAMILLE, locale: 'fr' }
    renderAt('/wish')

    expect(await screen.findByRole('heading', { name: /De quoi avez-vous/ })).toBeInTheDocument()
    expect(screen.getByText('Bonjour Camille')).toBeInTheDocument()
    expect(screen.getByLabelText('Votre envie de voyage')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Envoyer' })).toBeInTheDocument()
  })

  it('does not send an empty wish', async () => {
    renderAt('/wish')

    await writeAndSend('   ')

    expect(await screen.findByRole('alert')).toHaveTextContent('Describe what you')
    expect(posts('/wishes')).toHaveLength(0)
  })

  it('sends with Ctrl + Enter', async () => {
    renderAt('/wish')
    const box = await screen.findByLabelText('Your travel wish')
    fireEvent.change(box, { target: { value: 'La Crète en mai' } })

    fireEvent.keyDown(box, { key: 'Enter', ctrlKey: true })

    await waitFor(() => expect(posts('/wishes')).toHaveLength(1))
    expect(posts('/wishes')[0]!.body).toEqual({ text: 'La Crète en mai' })
  })

  it.each([
    ['Win32', 'Ctrl + Enter to send'],
    ['MacIntel', '⌘ + Enter to send'],
  ])('shows the shortcut of the platform (%s)', async (platform, hint) => {
    vi.spyOn(navigator, 'platform', 'get').mockReturnValue(platform)
    renderAt('/wish')

    expect(await screen.findByText((_, element) => element?.textContent === hint)).toBeInTheDocument()
  })

  it('opens the preferences when the destination is covered, keeping the wish for that page', async () => {
    const { router, queryClient } = renderAt('/wish')

    await writeAndSend('  Une semaine calme à Chania  ')

    expect(await screen.findByRole('heading', { name: /What matters/ })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe(`/wish/${WISH_ID}/preferences`)
    expect(queryClient.getQueryData<CachedWish>(wishQueryKey(WISH_ID))?.text).toBe('Une semaine calme à Chania')
    expect(screen.getByText('“Une semaine calme à Chania”')).toBeInTheDocument()
  })

  it('says when the destination is not covered and suggests covered ones', async () => {
    wishAnswer = () => Response.json(NOT_COVERED, { status: 201 })
    renderAt('/wish')

    await writeAndSend('Le Japon au printemps')

    expect(await screen.findByRole('heading', { name: /Kyoto makes us dream too/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Chania · Greece/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Marrakech · Morocco/ })).toBeInTheDocument()
  })

  it('starts a new wish from a suggestion', async () => {
    wishAnswer = () => Response.json(NOT_COVERED, { status: 201 })
    renderAt('/wish')
    await writeAndSend('Le Japon au printemps')

    fireEvent.click(await screen.findByRole('button', { name: /Marrakech · Morocco/ }))

    expect(await screen.findByLabelText('Your travel wish')).toHaveValue('A few days in Marrakech, ')
  })

  it('asks where when the wish names no place', async () => {
    wishAnswer = () =>
      Response.json({ id: 'x', status: 'draft', destination: null, suggestions: [], panel: null }, { status: 201 })
    renderAt('/wish')

    await writeAndSend('Quelque part au calme')

    expect(await screen.findByRole('status')).toHaveTextContent('Where would you like to go?')
  })

  it('explains a failure and lets the client try again', async () => {
    wishAnswer = () => Response.json({ code: 'internal_error', detail: 'boom' }, { status: 500 })
    renderAt('/wish')

    await writeAndSend('La Crète en mai')

    expect(await screen.findByRole('alert')).toHaveTextContent('couldn\'t be sent')
    expect(screen.getByLabelText('Your travel wish')).toHaveValue('La Crète en mai')
  })
})

describe('the preferences panel', () => {
  const withWish = (queryClient: QueryClient) =>
    queryClient.setQueryData<CachedWish>(wishQueryKey(WISH_ID), { ...PANEL_WISH, text: 'Une semaine à Chania' })

  function fillConstraints() {
    fireEvent.change(screen.getByLabelText(/Maximum budget/), { target: { value: '3 500 €' } })
    fireEvent.change(screen.getByLabelText('Departure'), { target: { value: '2027-05-12' } })
    fireEvent.change(screen.getByLabelText('Return'), { target: { value: '2027-05-19' } })
  }

  it('starts from the preselected tags and sends the chosen tags and constraints', async () => {
    const { router } = renderAt(`/wish/${WISH_ID}/preferences`, withWish)

    expect(await screen.findByRole('button', { name: /Calme/ })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Culture' }))
    fireEvent.click(screen.getByRole('button', { name: 'Très doux' }))
    fireEvent.click(screen.getByRole('button', { name: 'Dynamique' })) // single choice: replaces "Très doux"
    fireEvent.click(screen.getByRole('button', { name: 'One more traveller' }))
    fillConstraints()
    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    await waitFor(() => expect(router.state.location.pathname).toBe(`/plans/${PLAN_ID}`))
    expect(posts(`/wishes/${WISH_ID}/answers`)[0]!.body).toEqual({
      selected_tags: [
        { section: 'mood', tag: 'calm' },
        { section: 'mood', tag: 'culture' },
        { section: 'pace', tag: 'busy' },
      ],
      budget_max: '3500.00',
      currency: 'EUR',
      persons: 3,
      start_date: '2027-05-12',
      end_date: '2027-05-19',
    })
  })

  it('says the plan is being built while it waits, and sends only once', async () => {
    let finish!: (response: Response) => void
    answersAnswer = () => new Promise((resolve) => (finish = resolve))
    const { router } = renderAt(`/wish/${WISH_ID}/preferences`, withWish)
    await screen.findByRole('heading', { name: /What matters/ })
    fillConstraints()

    const send = screen.getByRole('button', { name: /Compose my preview/ })
    fireEvent.click(send)
    fireEvent.click(send)

    expect(await screen.findByRole('heading', { name: /Setting the evenings/ })).toHaveFocus()
    expect(screen.getByRole('status')).toHaveTextContent('up to a minute')
    expect(screen.queryByRole('button', { name: /Compose my preview/ })).not.toBeInTheDocument()
    expect(posts(`/wishes/${WISH_ID}/answers`)).toHaveLength(1)

    finish(Response.json(PLAN, { status: 201 }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/plans/${PLAN_ID}`))
  })

  it('keeps the answers when the plan could not be built, and lets the client try again', async () => {
    answersAnswer = () => Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
    renderAt(`/wish/${WISH_ID}/preferences`, withWish)
    await screen.findByRole('heading', { name: /What matters/ })
    fireEvent.click(screen.getByRole('button', { name: 'Culture' }))
    fillConstraints()

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent("We couldn't compose your plan")
    expect(screen.getByRole('alert')).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Culture' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText(/Maximum budget/)).toHaveValue('3 500 €')
    expect(screen.getByLabelText('Departure')).toHaveValue('2027-05-12')
    expect(screen.getByLabelText('Return')).toHaveValue('2027-05-19')

    answersAnswer = () => Response.json(PLAN, { status: 201 })
    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))
    await waitFor(() => expect(posts(`/wishes/${WISH_ID}/answers`)).toHaveLength(2))
  })

  it('says so when no offer fits, with the answers still filled in', async () => {
    answersAnswer = () => Response.json({ code: 'no_offer_fits', detail: 'nothing' }, { status: 422 })
    renderAt(`/wish/${WISH_ID}/preferences`, withWish)
    await screen.findByRole('heading', { name: /What matters/ })
    fillConstraints()

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('No offer fits these dates')
    expect(screen.getByLabelText('Departure')).toHaveValue('2027-05-12')
  })

  it('checks the constraints before sending', async () => {
    renderAt(`/wish/${WISH_ID}/preferences`, withWish)
    await screen.findByRole('heading', { name: /What matters/ })
    fillConstraints()
    fireEvent.change(screen.getByLabelText('Return'), { target: { value: '2027-05-01' } })

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    expect(await screen.findByText('The return must be after the departure.')).toBeInTheDocument()
    expect(screen.getByLabelText('Return')).toHaveAttribute('aria-invalid', 'true')
    expect(posts(`/wishes/${WISH_ID}/answers`)).toHaveLength(0)
  })

  it('explains an answer the API refuses', async () => {
    answersAnswer = () => Response.json({ code: 'invalid_answers', detail: 'bad tag' }, { status: 422 })
    renderAt(`/wish/${WISH_ID}/preferences`, withWish)
    await screen.findByRole('heading', { name: /What matters/ })
    fillConstraints()

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Check the dates and the budget')
  })

  it('says the plan may still be ready when the connection drops, keeping the answers', async () => {
    answersAnswer = () => {
      throw new TypeError('Failed to fetch')
    }
    renderAt(`/wish/${WISH_ID}/preferences`, withWish)
    await screen.findByRole('heading', { name: /What matters/ })
    fillConstraints()

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('It may still be ready')
    expect(screen.getByLabelText('Departure')).toHaveValue('2027-05-12')
  })

  it('asks to wait when the plan is still being composed by an earlier sending', async () => {
    answersAnswer = () => Response.json({ code: 'answer_in_progress', detail: 'busy' }, { status: 409 })
    renderAt(`/wish/${WISH_ID}/preferences`, withWish)
    await screen.findByRole('heading', { name: /What matters/ })
    fillConstraints()

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Your plan is still being composed')
  })

  it('leaves the client where they went when the plan is ready after they left', async () => {
    let finish!: (response: Response) => void
    answersAnswer = () => new Promise((resolve) => (finish = resolve))
    const { router } = renderAt(`/wish/${WISH_ID}/preferences`, withWish)
    await screen.findByRole('heading', { name: /What matters/ })
    fillConstraints()
    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))
    await screen.findByRole('heading', { name: /Setting the evenings/ })

    await router.navigate({ to: '/wish' })
    finish(Response.json(PLAN, { status: 201 }))

    await waitFor(() => expect(posts(`/wishes/${WISH_ID}/answers`)).toHaveLength(1))
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(router.state.location.pathname).toBe('/wish')
  })

  it('sends back to the wish when the panel is no longer known (page reloaded)', async () => {
    renderAt(`/wish/${WISH_ID}/preferences`)

    expect(await screen.findByRole('heading', { name: "Let's start again from your wish." })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Describe my trip' })).toHaveAttribute('href', '/wish')
  })
})

describe('the landing page', () => {
  it('shows the public page to visitors, with a way to sign in', async () => {
    signedIn = null
    renderAt('/')

    expect(await screen.findByRole('heading', { name: /Your wish/ })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('link', { name: /Continue with Google/ })).toHaveAttribute(
      'href',
      'http://api.test/auth/google/login?redirect_to=%2Fwish',
    )
  })

  it('offers the client space to a signed-in visitor', async () => {
    renderAt('/')

    expect(await screen.findByRole('link', { name: 'My space' })).toHaveAttribute('href', '/wish')
    expect(screen.queryByRole('link', { name: /Continue with Google/ })).not.toBeInTheDocument()
  })

  it('shows the agency e-mail in the footer, not the unchecked phone', async () => {
    signedIn = null
    renderAt('/')

    expect(await screen.findByRole('link', { name: 'contact@detour-voyages.fr' })).toHaveAttribute(
      'href',
      'mailto:contact@detour-voyages.fr',
    )
    expect(screen.getByRole('link', { name: 'Legal notices' })).toHaveAttribute('href', '/legal')
    expect(screen.queryByText(/02 40 00 00 00/)).not.toBeInTheDocument()
    expect(document.querySelector('img[src="/images/logo-1600.webp"]')).not.toBeNull()
  })

  it('names the client agency in the copy, not Novoya', async () => {
    signedIn = null
    renderAt('/')

    expect(await screen.findByText('The DÉTOUR promise')).toBeInTheDocument()
    expect(screen.queryByText(/Novoya/)).not.toBeInTheDocument()
    // The seal is the agency's own symbol, not a typed letter.
    expect(document.querySelector('img[src="/icon-192.png"]')).not.toBeNull()
  })

  it('opens the legal notices with confirmed facts only', async () => {
    signedIn = null
    renderAt('/legal')

    expect(await screen.findByRole('heading', { name: 'Legal notices' })).toBeInTheDocument()
    expect(screen.getByText(/This website is the website of DÉTOUR Voyages/)).toBeInTheDocument()
    const notices = within(document.querySelector('dl') as HTMLElement)
    expect(notices.getByText('DÉTOUR Voyages')).toBeInTheDocument()
    expect(notices.getByText('contact@detour-voyages.fr')).toBeInTheDocument()
    expect(notices.getByText('Novoya development team, on behalf of the Novoya project')).toBeInTheDocument()
    // No publication director until the agency names one: it is a legal role, not a credit.
    expect(notices.queryByText('Publication director')).not.toBeInTheDocument()
    expect(screen.queryByText(/IM044120000/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Écluses/)).not.toBeInTheDocument()
  })
})
