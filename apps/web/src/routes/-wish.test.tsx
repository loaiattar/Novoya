import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { getMeQueryKey } from '../api/generated/@tanstack/react-query.gen'
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
let wishAnswer: () => Response | Promise<Response>
let loginAnswer: () => Response
let answersAnswer: () => Response | Promise<Response>
// When set, GET /me waits for it: a guarded page then stays loading.
let meGate: Promise<void> | undefined

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    const text = request.method === 'POST' ? await request.text() : ''
    calls.push({ method: request.method, path, body: text ? JSON.parse(text) : undefined })
    if (path === '/me') {
      if (meGate) await meGate
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
  meGate = undefined
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

    expect(await screen.findByText(/Where would you like to go\?/)).toHaveAttribute('role', 'status')
  })

  it('explains a failure and lets the client try again', async () => {
    wishAnswer = () => Response.json({ code: 'internal_error', detail: 'boom' }, { status: 500 })
    renderAt('/wish')

    await writeAndSend('La Crète en mai')

    expect(await screen.findByRole('alert')).toHaveTextContent('couldn\'t be sent')
    expect(screen.getByLabelText('Your travel wish')).toHaveValue('La Crète en mai')
  })

  describe('while the wish is read', () => {
    let finish!: (response: Response) => void
    beforeEach(() => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'], shouldAdvanceTime: true })
      wishAnswer = () => new Promise<Response>((resolve) => (finish = resolve))
    })
    afterEach(() => {
      vi.useRealTimers()
    })

    const progress = () =>
      screen.getAllByRole('status').find((element) => element.textContent?.includes('…')) ?? null
    const showsStep = (step: string) => waitFor(() => expect(progress()).toHaveTextContent(step))

    it('shows the steps at once, and locks the box and the button', async () => {
      renderAt('/wish')

      await writeAndSend('La Crète en mai')

      await showsStep('Reading your wish')
      expect(screen.getByLabelText('Your travel wish')).toBeDisabled()
      expect(screen.getByRole('button', { name: 'Sending' })).toBeDisabled()
      // One spinner, the loader's: the send button does not turn as well.
      expect(screen.getByRole('button', { name: 'Sending' }).querySelector('[class*="animate-"]')).toBeNull()

      await act(() => vi.advanceTimersByTimeAsync(3000))
      expect(progress()).toHaveTextContent('Finding destinations')
      await act(() => vi.advanceTimersByTimeAsync(3000))
      expect(progress()).toHaveTextContent('Preparing your preferences')
      expect(posts('/wishes')).toHaveLength(1)
    })

    it('keeps the status region in place before the wish is sent, empty', async () => {
      renderAt('/wish')
      await screen.findByLabelText('Your travel wish')

      expect(screen.getByRole('status')).toBeEmptyDOMElement()
    })

    it('sends only once when the client sends twice before the page redraws', async () => {
      renderAt('/wish')
      const box = await screen.findByLabelText('Your travel wish')
      fireEvent.change(box, { target: { value: 'La Crète en mai' } })

      act(() => {
        fireEvent.keyDown(box, { key: 'Enter', ctrlKey: true })
        fireEvent.keyDown(box, { key: 'Enter', ctrlKey: true })
      })

      await showsStep('Reading your wish')
      expect(posts('/wishes')).toHaveLength(1)
    })

    it('goes away as soon as the answer arrives, whatever the step', async () => {
      const { router } = renderAt('/wish')
      await writeAndSend('Une semaine calme à Chania')
      await showsStep('Reading your wish')
      await act(() => vi.advanceTimersByTimeAsync(3000))
      expect(progress()).toHaveTextContent('Finding destinations')

      finish(Response.json(PANEL_WISH, { status: 201 }))

      expect(await screen.findByRole('heading', { name: /What matters/ })).toBeInTheDocument()
      expect(router.state.location.pathname).toBe(`/wish/${WISH_ID}/preferences`)
      expect(screen.queryByText(/Finding destinations/)).not.toBeInTheDocument()
    })

    it('gives the box back with a message and a way to try again when it fails', async () => {
      renderAt('/wish')
      await writeAndSend('La Crète en mai')
      await showsStep('Reading your wish')

      finish(Response.json({ code: 'internal_error', detail: 'boom' }, { status: 500 }))

      expect(await screen.findByRole('alert')).toHaveTextContent("couldn't be sent")
      expect(screen.queryByText(/Reading your wish/)).not.toBeInTheDocument()
      const box = screen.getByLabelText('Your travel wish')
      expect(box).toBeEnabled()
      await waitFor(() => expect(box).toHaveFocus())

      fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
      await showsStep('Reading your wish')
      finish(Response.json({ code: 'internal_error', detail: 'boom' }, { status: 500 }))
      expect(await screen.findByRole('alert')).toHaveTextContent("couldn't be sent")
      expect(posts('/wishes')).toHaveLength(2)
      expect(posts('/wishes')[1]!.body).toEqual({ text: 'La Crète en mai' })
    })

    it('gives the focus back to the box after asking where, and shows one status on the next send', async () => {
      renderAt('/wish')
      await writeAndSend('Quelque part au calme')
      await showsStep('Reading your wish')

      finish(Response.json({ id: 'x', status: 'draft', destination: null, suggestions: [], panel: null }, { status: 201 }))

      expect(await screen.findByText(/Where would you like to go\?/)).toBeInTheDocument()
      const box = screen.getByLabelText('Your travel wish')
      await waitFor(() => expect(box).toHaveFocus())

      fireEvent.change(box, { target: { value: 'Quelque part au calme, en Crète' } })
      fireEvent.click(screen.getByRole('button', { name: 'Send' }))

      await showsStep('Reading your wish')
      expect(screen.queryByText(/Where would you like to go\?/)).not.toBeInTheDocument()
      expect(screen.getAllByRole('status').filter((element) => element.textContent !== '')).toHaveLength(1)
    })

    it('locks the sparks while sending, and sends again once the answer is in', async () => {
      const { router } = renderAt('/wish')
      await writeAndSend('Quelque part au calme')
      await showsStep('Reading your wish')

      const spark = screen.getByRole('button', { name: 'Culture & calm' })
      expect(spark).toBeDisabled()
      fireEvent.click(spark)
      expect(screen.getByLabelText('Your travel wish')).toHaveValue('Quelque part au calme')

      finish(Response.json({ id: 'x', status: 'draft', destination: null, suggestions: [], panel: null }, { status: 201 }))
      expect(await screen.findByText(/Where would you like to go\?/)).toBeInTheDocument()
      expect(router.state.location.pathname).toBe('/wish')

      fireEvent.click(screen.getByRole('button', { name: 'Culture & calm' }))
      fireEvent.click(screen.getByRole('button', { name: 'Send' }))
      await showsStep('Reading your wish')
      expect(posts('/wishes')).toHaveLength(2)
      expect(posts('/wishes')[1]!.body).toEqual({ text: 'A few days in the sun, between culture and calm' })
    })

    it('can send again after starting over from a suggestion', async () => {
      renderAt('/wish')
      await writeAndSend('Le Japon au printemps')
      await showsStep('Reading your wish')
      finish(Response.json(NOT_COVERED, { status: 201 }))

      fireEvent.click(await screen.findByRole('button', { name: /Marrakech · Morocco/ }))
      fireEvent.change(await screen.findByLabelText('Your travel wish'), { target: { value: 'Marrakech en mai' } })
      fireEvent.click(screen.getByRole('button', { name: 'Send' }))

      await showsStep('Reading your wish')
      expect(posts('/wishes')).toHaveLength(2)
    })

    it('gives the focus back to the box when it stayed on the send button', async () => {
      renderAt('/wish')
      fireEvent.change(await screen.findByLabelText('Your travel wish'), { target: { value: 'La Crète en mai' } })
      const button = screen.getByRole('button', { name: 'Send' })
      button.focus()
      fireEvent.click(button)
      await showsStep('Reading your wish')

      finish(Response.json({ code: 'internal_error', detail: 'boom' }, { status: 500 }))

      expect(await screen.findByRole('alert')).toBeInTheDocument()
      await waitFor(() => expect(screen.getByLabelText('Your travel wish')).toHaveFocus())
    })

    it.each([
      ['a plan is ready', () => Response.json(PANEL_WISH, { status: 201 })],
      ['the session ended', () => Response.json({ code: 'unauthenticated', detail: 'expired' }, { status: 401 })],
    ])('leaves the client where they went when the answer comes after they left (%s)', async (_, answer) => {
      const { router } = renderAt('/wish')
      await writeAndSend('Une semaine calme à Chania')
      await showsStep('Reading your wish')

      fireEvent.click(screen.getByRole('link', { name: 'My trips' }))
      await waitFor(() => expect(router.state.location.pathname).toBe('/trips'))

      finish(answer())
      await act(() => vi.advanceTimersByTimeAsync(100))
      await waitFor(() => expect(router.state.status).toBe('idle'))
      expect(router.state.location.pathname).toBe('/trips')
    })

    it('forgets the session when it ended after the client left, so the next page asks to sign in', async () => {
      const { router } = renderAt('/wish')
      await writeAndSend('Une semaine calme à Chania')
      await showsStep('Reading your wish')
      fireEvent.click(screen.getByRole('link', { name: 'My trips' }))
      await waitFor(() => expect(router.state.location.pathname).toBe('/trips'))
      signedIn = null

      finish(Response.json({ code: 'unauthenticated', detail: 'expired' }, { status: 401 }))
      await act(() => vi.advanceTimersByTimeAsync(100))
      expect(router.state.location.pathname).toBe('/trips')

      fireEvent.click(screen.getByRole('link', { name: 'Compose' }))
      await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
      expect(router.state.location.search).toEqual({ redirect: '/wish' })
    })

    it('does not pull the client back while the page they went to is still loading', async () => {
      const { router, queryClient } = renderAt('/wish')
      await writeAndSend('Une semaine calme à Chania')
      await showsStep('Reading your wish')
      let openMe!: () => void
      meGate = new Promise((resolve) => (openMe = resolve))
      queryClient.removeQueries({ queryKey: getMeQueryKey() })

      void router.navigate({ to: '/trips' })
      await waitFor(() => expect(router.latestLocation.pathname).toBe('/trips'))
      // Still on screen: the next page waits for its guard.
      expect(screen.getByLabelText('Your travel wish')).toBeInTheDocument()

      finish(Response.json(PANEL_WISH, { status: 201 }))
      await act(() => vi.advanceTimersByTimeAsync(100))
      openMe()

      await waitFor(() => expect(router.state.status).toBe('idle'))
      await act(() => vi.advanceTimersByTimeAsync(100))
      expect(router.state.location.pathname).toBe('/trips')
    })

    it('lets the next page find the ended session itself when it is still asking for it', async () => {
      const { router, queryClient } = renderAt('/wish')
      await writeAndSend('Une semaine calme à Chania')
      await showsStep('Reading your wish')
      let openMe!: () => void
      meGate = new Promise((resolve) => (openMe = resolve))
      queryClient.removeQueries({ queryKey: getMeQueryKey() })

      void router.navigate({ to: '/trips' })
      await waitFor(() => expect(router.latestLocation.pathname).toBe('/trips'))
      signedIn = null

      finish(Response.json({ code: 'unauthenticated', detail: 'expired' }, { status: 401 }))
      await act(() => vi.advanceTimersByTimeAsync(100))
      openMe()

      await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
      expect(router.state.location.search).toEqual({ redirect: '/trips' })
    })

    it('leaves the focus where the client put it during the sending', async () => {
      renderAt('/wish')
      await writeAndSend('La Crète en mai')
      await showsStep('Reading your wish')
      const link = screen.getByRole('link', { name: 'My trips' })
      link.focus()

      finish(Response.json({ code: 'internal_error', detail: 'boom' }, { status: 500 }))

      expect(await screen.findByRole('alert')).toBeInTheDocument()
      await act(() => vi.advanceTimersByTimeAsync(50))
      expect(link).toHaveFocus()
    })

    it('shows the steps in French', async () => {
      signedIn = { ...CAMILLE, locale: 'fr' }
      renderAt('/wish')
      fireEvent.change(await screen.findByLabelText('Votre envie de voyage'), { target: { value: 'La Crète' } })
      fireEvent.click(screen.getByRole('button', { name: 'Envoyer' }))

      await showsStep('Nous lisons votre envie')
    })
  })

  it('offers to try again when the server is unavailable', async () => {
    wishAnswer = () => Response.json({ code: 'unavailable', detail: 'down' }, { status: 503 })
    renderAt('/wish')

    await writeAndSend('La Crète en mai')

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('offers to try again when the network fails', async () => {
    wishAnswer = () => {
      throw new TypeError('Failed to fetch')
    }
    renderAt('/wish')

    await writeAndSend('La Crète en mai')

    expect(await screen.findByRole('alert')).toHaveTextContent("couldn't be sent")
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('does not offer to try again when the API refuses the input', async () => {
    wishAnswer = () => Response.json({ code: 'invalid_input', detail: 'no' }, { status: 422 })
    renderAt('/wish')

    await writeAndSend('La Crète en mai')

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('sends the client to sign in again when the session ended during the sending', async () => {
    wishAnswer = () => Response.json({ code: 'unauthenticated', detail: 'expired' }, { status: 401 })
    const { router } = renderAt('/wish')
    await screen.findByLabelText('Your travel wish')
    signedIn = null

    await writeAndSend('La Crète en mai')

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: '/wish' })
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('does not offer to try again when the wish itself is refused', async () => {
    wishAnswer = () => Response.json({ code: 'invalid_wish', detail: 'no' }, { status: 422 })
    renderAt('/wish')

    await writeAndSend('La Crète en mai')

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('says how long to wait when the wish is rate limited', async () => {
    wishAnswer = () =>
      Response.json(
        { code: 'too_many_requests', detail: 'try again in 720 seconds' },
        { status: 429, headers: { 'Retry-After': '720' } },
      )
    renderAt('/wish')

    await writeAndSend('La Crète en mai')

    expect(await screen.findByRole('alert')).toHaveTextContent('Try again in 12 minutes')
    expect(screen.getByLabelText('Your travel wish')).toHaveValue('La Crète en mai')
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('keeps the usual wait message when Retry-After is missing', async () => {
    wishAnswer = () => Response.json({ code: 'too_many_requests', detail: 'slow down' }, { status: 429 })
    renderAt('/wish')

    await writeAndSend('La Crète en mai')

    expect(await screen.findByRole('alert')).toHaveTextContent('Please wait a moment and try again')
    expect(screen.getByLabelText('Your travel wish')).toHaveValue('La Crète en mai')
  })

  it('says how long to wait in French', async () => {
    signedIn = { ...CAMILLE, locale: 'fr' }
    wishAnswer = () =>
      Response.json(
        { code: 'too_many_requests', detail: 'try again in 12 seconds' },
        { status: 429, headers: { 'Retry-After': '12' } },
      )
    renderAt('/wish')

    fireEvent.change(await screen.findByLabelText('Votre envie de voyage'), { target: { value: 'La Crète en mai' } })
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Réessayez dans 12 secondes')
    expect(screen.getByLabelText('Votre envie de voyage')).toHaveValue('La Crète en mai')
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
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Reading your answers'))
    expect(screen.getByRole('status')).toHaveTextContent('up to a minute')
    expect(screen.queryByRole('button', { name: /Compose my preview/ })).not.toBeInTheDocument()
    expect(posts(`/wishes/${WISH_ID}/answers`)).toHaveLength(1)

    finish(Response.json(PLAN, { status: 201 }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/plans/${PLAN_ID}`))
  })

  it('shows the steps while the plan is built, and waits on the last one', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'], shouldAdvanceTime: true })
    try {
      let finish!: (response: Response) => void
      answersAnswer = () => new Promise((resolve) => (finish = resolve))
      const { router } = renderAt(`/wish/${WISH_ID}/preferences`, withWish)
      await screen.findByRole('heading', { name: /What matters/ })
      fillConstraints()

      fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

      await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Reading your answers'))
      await act(() => vi.advanceTimersByTimeAsync(8000))
      expect(screen.getByRole('status')).toHaveTextContent('Choosing among our partners')
      await act(() => vi.advanceTimersByTimeAsync(8000))
      expect(screen.getByRole('status')).toHaveTextContent('Setting your days')
      await act(() => vi.advanceTimersByTimeAsync(60_000))
      expect(screen.getByRole('status')).toHaveTextContent('Setting your days')

      finish(Response.json(PLAN, { status: 201 }))
      await waitFor(() => expect(router.state.location.pathname).toBe(`/plans/${PLAN_ID}`))
    } finally {
      vi.useRealTimers()
    }
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

  it('says how long to wait when the answers are rate limited, with the form still filled in', async () => {
    answersAnswer = () =>
      Response.json(
        { code: 'too_many_requests', detail: 'try again in 720 seconds' },
        { status: 429, headers: { 'Retry-After': '720' } },
      )
    renderAt(`/wish/${WISH_ID}/preferences`, withWish)
    await screen.findByRole('heading', { name: /What matters/ })
    fireEvent.click(screen.getByRole('button', { name: 'Culture' }))
    fillConstraints()

    fireEvent.click(screen.getByRole('button', { name: /Compose my preview/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Try again in 12 minutes')
    expect(screen.getByRole('button', { name: 'Culture' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText(/Maximum budget/)).toHaveValue('3 500 €')
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

    expect(await screen.findByRole('heading', { name: /the best part of travel/i })).toBeInTheDocument()
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

  it('shows the agency e-mail and phone in the footer', async () => {
    signedIn = null
    renderAt('/')

    expect(await screen.findByRole('link', { name: 'contact@detour-voyages.fr' })).toHaveAttribute(
      'href',
      'mailto:contact@detour-voyages.fr',
    )
    expect(screen.getByRole('link', { name: 'Legal notices' })).toHaveAttribute('href', '/legal')
    expect(screen.getByRole('link', { name: '02 40 00 00 00' })).toHaveAttribute('href', 'tel:+33240000000')
  })

  it('names the client agency in the copy, not Novoya', async () => {
    signedIn = null
    renderAt('/')

    expect(await screen.findByText(/then a DÉTOUR advisor makes it happen/)).toBeInTheDocument()
    expect(screen.queryByText(/Novoya/)).not.toBeInTheDocument()
  })

  it('credits the Novoya team in French on the legal notices', async () => {
    signedIn = null
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['fr-FR'])
    renderAt('/legal')

    const notices = within((await screen.findByRole('main')).querySelector('dl') as HTMLElement)
    expect(await notices.findByText('L’équipe Novoya, pour DÉTOUR')).toBeInTheDocument()
    expect(screen.queryByText(/équipe de développement DÉTOUR/)).not.toBeInTheDocument()
  })

  it('opens the legal notices with confirmed facts only', async () => {
    signedIn = null
    renderAt('/legal')

    expect(await screen.findByRole('heading', { name: 'Legal notices' })).toBeInTheDocument()
    expect(screen.getByText(/This website is the website of DÉTOUR Voyages/)).toBeInTheDocument()
    const notices = within(document.querySelector('main dl') as HTMLElement)
    expect(notices.getByText('DÉTOUR Voyages')).toBeInTheDocument()
    expect(notices.getByText('contact@detour-voyages.fr')).toBeInTheDocument()
    // The site was made by the Novoya team for the agency: the agency has no development team.
    expect(notices.getByText('The Novoya team, for DÉTOUR')).toBeInTheDocument()
    expect(screen.queryByText(/DÉTOUR development team/)).not.toBeInTheDocument()
    expect(screen.getByText(/This website is the website of DÉTOUR Voyages/).textContent).toBe(
      'This website is the website of DÉTOUR Voyages. It was designed and developed by the Novoya team.',
    )
    expect(notices.queryByText('Publication director')).not.toBeInTheDocument()
    expect(notices.getByText('12 rue des Écluses, 44000 Nantes')).toBeInTheDocument()
    expect(screen.queryByText(/IM044120000/)).not.toBeInTheDocument()
  })
})
