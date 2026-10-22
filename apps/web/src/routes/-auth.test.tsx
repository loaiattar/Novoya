import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { getMeQueryKey } from '../api/generated/@tanstack/react-query.gen'
import { client } from '../api/generated/client.gen'
import type { MeResponse } from '../api/generated/types.gen'
import { createAppRouter } from '../router'

const LEA: MeResponse = {
  id: '6f1c2b1e-0000-4000-8000-000000000001',
  email: 'lea@example.com',
  name: 'Léa Martin',
  first_name: 'Léa',
  last_name: 'Martin',
  role: 'client',
  locale: 'en',
  status: 'active',
  email_verified: true,
  created_at: '2026-10-01T10:00:00Z',
  sign_in_methods: ['google'],
}

type Answer = 'ok' | 'server_error' | 'network_error'
type MeAnswer = Answer | 'other_401' | 'forbidden'

let signedIn: MeResponse | null
let meAnswer: MeAnswer
let logoutAnswer: Answer
/** While set, POST /auth/logout waits for it: the sign-out stays pending. */
let logoutGate: Promise<void> | null
let calls: string[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    calls.push(`${request.method} ${path}`)
    if (path === '/me') {
      if (meAnswer === 'network_error') throw new TypeError('Failed to fetch')
      if (meAnswer === 'server_error') {
        return Response.json({ code: 'internal_error', detail: 'boom' }, { status: 500 })
      }
      if (meAnswer === 'other_401') {
        return Response.json({ code: 'invalid_credentials', detail: 'odd' }, { status: 401 })
      }
      if (meAnswer === 'forbidden') {
        return Response.json({ code: 'forbidden', detail: 'not allowed' }, { status: 403 })
      }
      return signedIn
        ? Response.json(signedIn)
        : Response.json({ code: 'unauthenticated', detail: 'not signed in' }, { status: 401 })
    }
    if (path === '/auth/logout') {
      if (logoutGate) await logoutGate
      if (logoutAnswer === 'network_error') throw new TypeError('Failed to fetch')
      if (logoutAnswer === 'server_error') {
        return Response.json({ code: 'internal_error', detail: 'boom' }, { status: 500 })
      }
      signedIn = null
      return new Response(null, { status: 204 })
    }
    return Response.json({ status: 'ok' })
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
  return { router, queryClient }
}

/** The account menu is a Radix dropdown: it opens on pointer down, not on click. */
async function openAccountMenu() {
  const trigger = await screen.findByRole('button', { name: /Léa|lea@example\.com/ })
  fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false })
}

async function signOutFromMenu(label = 'Sign out') {
  await openAccountMenu()
  fireEvent.click(await screen.findByRole('menuitem', { name: label }))
}

const meCalls = () => calls.filter((call) => call === 'GET /me').length
const logoutCalls = () => calls.filter((call) => call === 'POST /auth/logout').length

describe('sign-in and sign-out', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    signedIn = null
    meAnswer = 'ok'
    logoutAnswer = 'ok'
    logoutGate = null
    calls = []
    mockApi()
  })
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('sends a signed-out visitor of a protected page to the login page', async () => {
    const { router } = renderAt('/wish')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.search).toEqual({ redirect: '/wish' })
  })

  it('keeps the search of the requested page in the redirect', async () => {
    const { router } = renderAt('/wish?trip=beach')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.search).toEqual({ redirect: '/wish?trip=beach' })
  })

  it.each<MeAnswer>(['other_401', 'forbidden'])(
    'shows the error page, not the login page, for any error but a 401 unauthenticated (%s)',
    async (answer) => {
      meAnswer = answer
      const { router } = renderAt('/wish')

      expect(await screen.findByRole('alert')).toHaveTextContent("can't reach the server")
      expect(router.state.location.pathname).toBe('/wish')
      expect(screen.queryByRole('heading', { name: 'Sign in' })).not.toBeInTheDocument()
    },
  )

  it.each<Answer>(['server_error', 'network_error'])(
    'shows the error page, not the login page, when /me fails on a protected page (%s)',
    async (answer) => {
      meAnswer = answer
      const { router } = renderAt('/wish')

      expect(await screen.findByRole('alert')).toHaveTextContent("can't reach the server")
      expect(router.state.location.pathname).toBe('/wish')
      expect(screen.queryByRole('heading', { name: 'Sign in' })).not.toBeInTheDocument()
    },
  )

  it.each<Answer>(['server_error', 'network_error'])(
    'shows the error page when /me fails on the login page (%s)',
    async (answer) => {
      meAnswer = answer
      renderAt('/login')

      expect(await screen.findByRole('alert')).toHaveTextContent("can't reach the server")
      expect(screen.queryByRole('link', { name: 'Continue with Google' })).not.toBeInTheDocument()
    },
  )

  it('opens the page once the API answers again', async () => {
    meAnswer = 'server_error'
    signedIn = LEA
    renderAt('/wish')

    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))
    meAnswer = 'ok'
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { name: /What would you/ })).toBeInTheDocument()
  })

  it('starts Google sign-in and comes back to the requested page', async () => {
    renderAt('/login?redirect=%2Fwishes%3Fid%3D1')

    const link = await screen.findByRole('link', { name: 'Continue with Google' })
    expect(link).toHaveAttribute(
      'href',
      'http://api.test/auth/google/login?redirect_to=%2Fwishes%3Fid%3D1',
    )
  })

  it('never sends the user to another site after signing in', async () => {
    renderAt('/login?redirect=%2F%2Fevil.com')

    const link = await screen.findByRole('link', { name: 'Continue with Google' })
    expect(link).toHaveAttribute('href', 'http://api.test/auth/google/login?redirect_to=%2Fwish')
  })

  it('explains why a Google sign-in failed', async () => {
    renderAt('/login?error=oauth_failed')

    expect(await screen.findByRole('alert')).toHaveTextContent('Google sign-in did not work')
  })

  it('says so when the user cancelled at Google', async () => {
    renderAt('/login?error=oauth_cancelled')

    expect(await screen.findByRole('alert')).toHaveTextContent('You cancelled the Google sign-in.')
  })

  it('skips the login page when already signed in', async () => {
    signedIn = LEA
    const { router } = renderAt('/login')

    expect(await screen.findByRole('heading', { name: /What would you/ })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/wish')
  })

  it('sends a signed-in user on /login back to the requested page', async () => {
    signedIn = LEA
    const { router } = renderAt('/login?redirect=%2Fwish%3Ftrip%3Dbeach')

    expect(await screen.findByRole('heading', { name: /What would you/ })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/wish')
    expect(router.state.location.search).toEqual({ trip: 'beach' })
  })

  it('never sends a signed-in user on /login to another site', async () => {
    signedIn = LEA
    const { router } = renderAt('/login?redirect=%2F%2Fevil.com')

    expect(await screen.findByRole('heading', { name: /What would you/ })).toBeInTheDocument()
    expect(router.state.location.href).toBe('/wish')
  })

  it('shows the signed-in user in the header', async () => {
    signedIn = LEA
    renderAt('/wish')

    expect(await screen.findByText('Léa')).toBeInTheDocument()
  })

  it('shows the first word of name when first_name is missing', async () => {
    signedIn = { ...LEA, first_name: null }
    renderAt('/wish')

    expect(await screen.findByText('Léa')).toBeInTheDocument()
  })

  it('shows the email when the user has no name', async () => {
    signedIn = { ...LEA, first_name: null, name: null }
    renderAt('/wish')

    expect(await screen.findByText('lea@example.com')).toBeInTheDocument()
  })

  it('signs out, forgets the user and returns to the login page', async () => {
    signedIn = LEA
    const { router, queryClient } = renderAt('/wish')

    await signOutFromMenu()

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(calls).toContain('POST /auth/logout')
    expect(router.state.location.pathname).toBe('/login')
    expect(screen.queryByText('Léa')).not.toBeInTheDocument()
    expect(queryClient.getQueryData(getMeQueryKey())).toBeUndefined()
  })

  it.each<Answer>(['server_error', 'network_error'])(
    'stays signed in and says so when signing out fails (%s)',
    async (answer) => {
      signedIn = LEA
      logoutAnswer = answer
      const { router } = renderAt('/wish')

      await signOutFromMenu()

      expect(await screen.findByRole('alert')).toHaveTextContent('Sign out failed. Please try again.')
      expect(router.state.location.pathname).toBe('/wish')
      expect(screen.getByText('Léa')).toBeInTheDocument()
    },
  )

  it('sends a single sign-out request when sign-out is chosen twice', async () => {
    signedIn = LEA
    let release!: () => void
    logoutGate = new Promise((resolve) => (release = resolve))
    renderAt('/wish')

    await signOutFromMenu()
    await openAccountMenu()
    const pending = await screen.findByRole('menuitem', { name: 'Signing out…' })
    expect(pending).toHaveAttribute('aria-disabled', 'true')
    fireEvent.click(pending)
    release()

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(logoutCalls()).toBe(1)
  })

  it('signs out on the second try after a failure, and drops the error', async () => {
    signedIn = LEA
    logoutAnswer = 'server_error'
    const { router } = renderAt('/wish')

    await signOutFromMenu()
    expect(await screen.findByRole('alert')).toHaveTextContent('Sign out failed')

    logoutAnswer = 'ok'
    await signOutFromMenu()

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(screen.queryByText(/Sign out failed/)).not.toBeInTheDocument()
    expect(logoutCalls()).toBe(2)
  })

  it('keeps a way home on the error page when the session check fails', async () => {
    meAnswer = 'server_error'
    renderAt('/wish')

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'DÉTOUR, home' })).toHaveAttribute('href', '/')
  })

  describe('the public landing page', () => {
    it('lets a visitor in without a session and offers to sign in', async () => {
      const { router } = renderAt('/')

      expect(await screen.findByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
      expect(router.state.location.pathname).toBe('/')
    })

    it('sends a signed-in user to their space instead', async () => {
      signedIn = LEA
      renderAt('/')

      expect(await screen.findByRole('link', { name: 'My space' })).toHaveAttribute('href', '/wish')
      expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument()
    })
  })

  describe('header links by role', () => {
    const navLinks = async () => {
      const nav = await screen.findByRole('navigation', { name: 'Main navigation' })
      return Array.from(nav.querySelectorAll('a')).map((link) => link.textContent)
    }

    it('shows a client only the composer and their trips', async () => {
      signedIn = LEA
      renderAt('/wish')

      expect(await navLinks()).toEqual(['Compose', 'My trips'])
    })

    it('adds the agency space for an agent', async () => {
      signedIn = { ...LEA, role: 'agent' }
      renderAt('/wish')

      expect(await navLinks()).toEqual(['Compose', 'My trips', 'Agency'])
    })

    it('adds the agency space and administration for an admin', async () => {
      signedIn = { ...LEA, role: 'admin' }
      renderAt('/wish')

      expect(await navLinks()).toEqual(['Compose', 'My trips', 'Agency', 'Administration'])
    })
  })

  describe('language', () => {
    const browserLanguages = (languages: string[]) =>
      vi.spyOn(navigator, 'languages', 'get').mockReturnValue(languages)

    it("shows the app in the signed-in user's language", async () => {
      signedIn = { ...LEA, locale: 'fr' }
      browserLanguages(['en-US'])
      renderAt('/wish')

      expect(await screen.findByRole('heading', { name: /De quoi avez-vous/ })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Mes voyages' })).toBeInTheDocument()
      expect(document.documentElement).toHaveAttribute('lang', 'fr')
    })

    it("prefers the user's locale to the browser's language", async () => {
      signedIn = { ...LEA, locale: 'en' }
      browserLanguages(['fr-FR'])
      renderAt('/wish')

      expect(await screen.findByRole('heading', { name: /What would you/ })).toBeInTheDocument()
      expect(document.documentElement).toHaveAttribute('lang', 'en')
    })

    it("uses the browser's language when signed out", async () => {
      browserLanguages(['fr-FR', 'en'])
      renderAt('/login')

      expect(await screen.findByRole('heading', { name: 'Se connecter' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Continuer avec Google' })).toBeInTheDocument()
      expect(document.documentElement).toHaveAttribute('lang', 'fr')
    })

    it("shows the landing page in the browser's language", async () => {
      browserLanguages(['fr-FR'])
      renderAt('/')

      expect(await screen.findByRole('link', { name: 'Décrire mon voyage' })).toHaveAttribute('href', '/wish')
    })

    it('translates the sign-in error sent by the API', async () => {
      browserLanguages(['fr-FR'])
      renderAt('/login?error=oauth_cancelled')

      expect(await screen.findByRole('alert')).toHaveTextContent('Vous avez annulé la connexion avec Google.')
    })

    it("goes back to the browser's language after signing out", async () => {
      signedIn = { ...LEA, locale: 'fr' }
      browserLanguages(['en-US'])
      renderAt('/wish')

      await signOutFromMenu('Se déconnecter')

      expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
      expect(document.documentElement).toHaveAttribute('lang', 'en')
    })
  })

  describe('after 3 minutes without any action', () => {
    beforeEach(() => {
      vi.useFakeTimers({ toFake: ['Date'] })
      vi.setSystemTime(new Date('2026-10-19T10:00:00Z'))
    })

    it('does not ask /me again while the user keeps acting', async () => {
      signedIn = LEA
      renderAt('/wish')
      await screen.findByText('Léa')

      vi.advanceTimersByTime(2 * 60_000)
      fireEvent.pointerMove(window)
      fireEvent.click(screen.getByRole('link', { name: 'Compose' }))

      await screen.findByRole('heading', { name: /What would you/ })
      expect(meCalls()).toBe(1)
    })

    it('checks the session again and stays on the page while it is valid', async () => {
      signedIn = LEA
      const { router } = renderAt('/wish')
      await screen.findByText('Léa')

      vi.advanceTimersByTime(3 * 60_000)
      fireEvent.pointerMove(window)
      fireEvent.click(screen.getByRole('link', { name: 'Compose' }))

      await waitFor(() => expect(meCalls()).toBe(2))
      expect(router.state.location.pathname).toBe('/wish')
      expect(screen.getByText('Léa')).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: /What would you/ })).toBeInTheDocument()
    })

    it('checks the session again and goes to /login if it was revoked', async () => {
      signedIn = LEA
      const { router } = renderAt('/wish')
      await screen.findByText('Léa')

      signedIn = null // signed out on another device
      vi.advanceTimersByTime(3 * 60_000)
      fireEvent.pointerMove(window)
      fireEvent.click(screen.getByRole('link', { name: 'Compose' }))

      expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
      expect(router.state.location.pathname).toBe('/login')
      // Asked again by the guard (401), then by /login itself.
      await waitFor(() => expect(meCalls()).toBeGreaterThan(1))
    })
  })
})
