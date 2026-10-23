import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import type { AdvisorResponse } from '../api/generated'
import { client } from '../api/generated/client.gen'
import i18n from '../i18n'
import { createAppRouter } from '../router'

// What GET /advisors answers. Every advisor is made up.
const ADVISORS: AdvisorResponse[] = [
  {
    id: '00000000-0000-4000-8000-000000000061',
    name: 'Camille Durand',
    title: 'Fondatrice et responsable',
    summary: 'Toujours à la recherche de la prochaine pépite.',
    services: [
      { fr: 'Grèce', en: 'Greece' },
      { fr: 'Week-ends en amoureux', en: null },
      { fr: null, en: 'Train journeys' },
    ],
  },
  { id: '00000000-0000-4000-8000-000000000062', name: 'Yanis', title: null, summary: null, services: [] },
]

let router: ReturnType<typeof createAppRouter> | undefined
let advisorsAnswer: () => Response

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    if (path === '/me') return Response.json({ code: 'unauthenticated', detail: 'no session' }, { status: 401 })
    if (path === '/advisors') return advisorsAnswer()
    return Response.json([])
  })
}

function renderHome() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: ['/'] }))
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('the advisors on the home page', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en')
    client.setConfig({ baseUrl: 'http://api.test' })
    advisorsAnswer = () => Response.json(ADVISORS)
    mockApi()
  })
  afterEach(async () => {
    await waitFor(() => expect(router?.state.status).toBe('idle'))
    await i18n.changeLanguage('en')
    vi.restoreAllMocks()
  })

  it('shows each advisor with their initials, title, summary and services', async () => {
    renderHome()

    const section = (await screen.findByRole('heading', { name: 'The people behind every detour.' })).closest('section')!
    const camille = within(section).getByRole('heading', { name: 'Camille Durand' }).closest('li')!
    expect(within(camille).getByText('CD')).toBeInTheDocument()
    expect(within(camille).getByText('Fondatrice et responsable')).toBeInTheDocument()
    expect(within(camille).getByText('Toujours à la recherche de la prochaine pépite.')).toBeInTheDocument()
    const services = within(camille).getByRole('list', { name: 'Their specialities' })
    expect(within(services).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Greece',
      'Week-ends en amoureux',
      'Train journeys',
    ])
    // A service given in French only keeps its language for screen readers.
    expect(within(services).getByText('Week-ends en amoureux')).toHaveAttribute('lang', 'fr')

    // No title given: the default one, translated. No summary nor services: nothing more.
    const yanis = within(section).getByRole('heading', { name: 'Yanis' }).closest('li')!
    expect(within(yanis).getByText('Travel advisor')).toBeInTheDocument()
    expect(within(yanis).queryByRole('list')).toBeNull()

    // The header names the team, as text and not as a link.
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(within(nav).getByText('Our advisors').tagName).toBe('SPAN')
    expect(within(nav).queryByRole('link', { name: 'Our advisors' })).toBeNull()
  })

  it('shows each service in French, falling back to English', async () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['fr-FR'])
    await i18n.changeLanguage('fr')
    renderHome()

    const section = (await screen.findByRole('heading', { name: 'Des humains derrière chaque détour.' })).closest(
      'section',
    )!
    const services = within(section).getAllByRole('list', { name: 'Ses spécialités' })[0]!
    expect(within(services).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Grèce',
      'Week-ends en amoureux',
      'Train journeys',
    ])
    expect(within(services).getByText('Train journeys')).toHaveAttribute('lang', 'en')
    expect(within(section).getByText('Conseiller voyage')).toBeInTheDocument()
  })

  it('hides the section and the header text when no advisor is shown', async () => {
    advisorsAnswer = () => Response.json([])
    renderHome()

    expect(await screen.findByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument()
    await waitFor(() => expect(router?.state.status).toBe('idle'))
    expect(screen.queryByRole('heading', { name: 'The people behind every detour.' })).toBeNull()
    expect(screen.queryByText('Our advisors')).toBeNull()
  })

  it('hides the section when the request fails', async () => {
    advisorsAnswer = () => Response.json({ code: 'unavailable', detail: 'down' }, { status: 503 })
    renderHome()

    expect(await screen.findByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'The people behind every detour.' })).toBeNull()
  })
})
