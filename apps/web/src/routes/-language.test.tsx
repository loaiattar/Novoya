import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse } from '../api/generated/types.gen'
import i18n from '../i18n'
import { createAppRouter } from '../router'

const CAMILLE: MeResponse = {
  id: '6f1c2b1e-0000-4000-8000-000000000003',
  email: 'camille@exemple.fr',
  name: 'Camille Durand',
  first_name: 'Camille',
  last_name: 'Durand',
  role: 'client',
  locale: 'en',
  status: 'active',
  email_verified: true,
  created_at: '2026-10-01T10:00:00Z',
  sign_in_methods: ['password'],
}

type Call = { method: string; path: string; body: unknown }

let signedIn: MeResponse | null
let calls: Call[]
let patchAnswer: (body: { locale: 'en' | 'fr' }) => Response
let router: ReturnType<typeof createAppRouter> | undefined

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    const text = request.method === 'GET' ? '' : await request.text()
    const body = text ? JSON.parse(text) : undefined
    calls.push({ method: request.method, path, body })
    if (path === '/me' && request.method === 'PATCH') return patchAnswer(body)
    if (path === '/me') {
      return signedIn
        ? Response.json(signedIn)
        : Response.json({ code: 'unauthenticated', detail: 'not signed in' }, { status: 401 })
    }
    return Response.json([])
  })
}

function renderAt(url: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [url] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

// Public pages have a switch in the header and in the footer: the first one is enough here.
const languageSwitch = async (name: 'Language' | 'Langue') => (await screen.findAllByRole('group', { name }))[0]

describe('the language switch', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    signedIn = null
    calls = []
    patchAnswer = (body) => {
      signedIn = { ...CAMILLE, locale: body.locale }
      return Response.json(signedIn)
    }
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['en-US'])
    mockApi()
  })
  // Let navigations and router.invalidate() finish before jsdom is torn down.
  afterEach(async () => {
    await waitFor(() => expect(router?.state.status).toBe('idle'))
    vi.restoreAllMocks()
  })

  it.each(['/', '/destinations'])('is in the header and the footer of %s', async (url) => {
    renderAt(url)

    const header = await screen.findByRole('banner')
    expect(within(header).getByRole('group', { name: 'Language' })).toBeInTheDocument()
    expect(within(screen.getByRole('contentinfo')).getByRole('group', { name: 'Language' })).toBeInTheDocument()
  })

  it('switching in the header also updates the footer', async () => {
    renderAt('/destinations')

    const header = await screen.findByRole('banner')
    fireEvent.click(within(header).getByRole('button', { name: /Français/ }))

    const footer = screen.getByRole('contentinfo')
    await waitFor(() =>
      expect(within(footer).getByRole('button', { name: /Français/ })).toHaveAttribute('aria-pressed', 'true'),
    )
  })

  it('marks the current language', async () => {
    renderAt('/destinations')

    const group = await languageSwitch('Language')
    expect(within(group).getByRole('button', { name: /English/ })).toHaveAttribute('aria-pressed', 'true')
    expect(within(group).getByRole('button', { name: /Français/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('signed out: switches the texts and <html lang> without calling the API', async () => {
    renderAt('/destinations')

    fireEvent.click(within(await languageSwitch('Language')).getByRole('button', { name: /Français/ }))

    expect(await screen.findByRole('link', { name: 'Week-ends surprises' })).toBeInTheDocument()
    expect(within(await languageSwitch('Langue')).getByRole('button', { name: /Français/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(document.documentElement).toHaveAttribute('lang', 'fr')
    expect(calls.filter((call) => call.method === 'PATCH')).toEqual([])
  })

  it('signed out: the choice is kept after a reload, over the browser language', async () => {
    renderAt('/destinations')
    fireEvent.click(within(await languageSwitch('Language')).getByRole('button', { name: /Français/ }))
    await screen.findByRole('link', { name: 'Week-ends surprises' })

    // A reload: the page goes away and the app starts again in the browser's language.
    cleanup()
    await i18n.changeLanguage('en')
    renderAt('/destinations')

    expect(await screen.findByRole('link', { name: 'Week-ends surprises' })).toBeInTheDocument()
  })

  it('signed in: saves the language with PATCH /me, then switches', async () => {
    signedIn = CAMILLE
    renderAt('/trips')

    const group = await languageSwitch('Language')
    expect(screen.getAllByRole('link', { name: 'My trips' }).length).toBeGreaterThan(0)
    fireEvent.click(within(group).getByRole('button', { name: /Français/ }))

    await waitFor(() => expect(screen.getAllByRole('link', { name: 'Mes voyages' }).length).toBeGreaterThan(0))
    expect(calls.filter((call) => call.method === 'PATCH')).toEqual([
      { method: 'PATCH', path: '/me', body: { locale: 'fr' } },
    ])
    expect(document.documentElement).toHaveAttribute('lang', 'fr')

    // The next page reads the saved user: it stays in French.
    fireEvent.click(screen.getAllByRole('link', { name: 'Composer' })[0])
    await waitFor(() => expect(router?.state.location.pathname).not.toBe('/trips'))
    await waitFor(() => expect(screen.getAllByRole('group', { name: 'Langue' }).length).toBeGreaterThan(0))
    expect(i18n.language).toBe('fr')
  })

  it('signed in: keeps the language and says so when it could not be saved', async () => {
    signedIn = CAMILLE
    patchAnswer = () => Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
    renderAt('/trips')

    fireEvent.click(within(await languageSwitch('Language')).getByRole('button', { name: /Français/ }))

    expect(await screen.findByText('The language could not be changed.')).toBeInTheDocument()
    expect(i18n.language).toBe('en')
  })
})
