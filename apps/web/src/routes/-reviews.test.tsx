import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import { createAppRouter } from '../router'

// What GET /reviews answers, newest first. Every review and author is made up.
const REVIEWS = [
  {
    id: '00000000-0000-4000-8000-000000000051',
    country: 'Greece',
    city: 'Chania',
    rating: 3,
    reviewed_on: '2026-08-20',
    text: 'Plus récent, inventé.',
    author: 'Voyageur anonyme',
  },
  {
    id: '00000000-0000-4000-8000-000000000052',
    country: 'France',
    city: 'Saint-Jean de Luz',
    rating: 4,
    reviewed_on: '2026-07-15',
    text: 'Très bon accueil, inventé aussi.',
    author: 'Voyageur anonyme',
  },
  {
    id: '00000000-0000-4000-8000-000000000053',
    country: 'Greece',
    city: 'Chania',
    rating: 5,
    reviewed_on: '2026-06-01',
    text: 'Un séjour parfait, inventé pour les tests.',
    author: 'Zélie Q.',
  },
]

let requests: string[]
let reviewsAnswer: () => Response

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    requests.push(path)
    if (path === '/me') return Response.json({ code: 'unauthenticated', detail: 'no session' }, { status: 401 })
    if (path === '/reviews') return reviewsAnswer()
    if (path === '/destinations') {
      return Response.json([
        { country: 'France', city: 'Saint-Jean de Luz' },
        { country: 'Greece', city: 'Chania' },
      ])
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
  return { router }
}

describe('destinations and reviews page', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    requests = []
    reviewsAnswer = () => Response.json(REVIEWS)
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('is public: a visitor without a session sees the reviews', async () => {
    const { router } = renderAt('/destinations')

    expect(await screen.findByText('Un séjour parfait, inventé pour les tests.')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/destinations')
    expect(requests).toContain('/reviews')
  })

  it('groups the reviews by destination', async () => {
    renderAt('/destinations')

    const chania = await screen.findByRole('region', { name: /Chania/ })
    const luz = screen.getByRole('region', { name: /Saint-Jean de Luz/ })
    expect(within(chania).getByText('Plus récent, inventé.')).toBeInTheDocument()
    expect(within(chania).getByText('Un séjour parfait, inventé pour les tests.')).toBeInTheDocument()
    expect(within(chania).queryByText('Très bon accueil, inventé aussi.')).not.toBeInTheDocument()
    expect(within(luz).getByText('Très bon accueil, inventé aussi.')).toBeInTheDocument()
  })

  it('shows each author exactly as given, untranslated', async () => {
    renderAt('/destinations')

    const chania = await screen.findByRole('region', { name: /Chania/ })
    expect(within(chania).getByText('Zélie Q.')).toBeInTheDocument()
    expect(within(chania).getByText('Voyageur anonyme')).toBeInTheDocument()
  })

  it('has a visible link back to the home page', async () => {
    const { router } = renderAt('/destinations')

    fireEvent.click(await screen.findByRole('link', { name: '← Back to home' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })

  it('is linked from the footer of the public pages', async () => {
    renderAt('/')

    const link = await screen.findByRole('link', { name: /destinations/i })
    expect(link).toHaveAttribute('href', '/destinations')
  })

  it('names the destinations and dates in French for a French visitor, authors untouched', async () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['fr-FR'])
    renderAt('/destinations')

    const chania = await screen.findByRole('region', { name: 'Chania, Grèce' })
    expect(within(chania).getByText('1 juin 2026')).toBeInTheDocument()
    expect(within(chania).getByText('Voyageur anonyme')).toBeInTheDocument()
    expect(within(chania).getByRole('img', { name: 'Noté 5 sur 5' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Saint-Jean de Luz, France' })).toBeInTheDocument()
  })

  it('says each review is in French when the page is in English', async () => {
    renderAt('/destinations')

    const text = await screen.findByText('Un séjour parfait, inventé pour les tests.')
    expect(text).toHaveAttribute('lang', 'fr')
    expect(screen.getAllByText('Review in French')).toHaveLength(REVIEWS.length)
  })

  it('has no language note when the page is in French', async () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['fr-FR'])
    renderAt('/destinations')

    expect(await screen.findByText('Un séjour parfait, inventé pour les tests.')).toHaveAttribute('lang', 'fr')
    expect(screen.queryByText('Review in French')).not.toBeInTheDocument()
    expect(screen.queryByText(/en français/i)).not.toBeInTheDocument()
  })

  it('says so when no review is published yet', async () => {
    reviewsAnswer = () => Response.json([])
    renderAt('/destinations')

    expect(await screen.findByText('No review has been published yet.')).toBeInTheDocument()
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
  })

  it('lets the visitor try again when the reviews could not be loaded', async () => {
    reviewsAnswer = () => Response.json({ code: 'unknown', detail: 'boom' }, { status: 500 })
    renderAt('/destinations')

    expect(await screen.findByText('The reviews could not be loaded.')).toBeInTheDocument()
    reviewsAnswer = () => Response.json(REVIEWS)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('region', { name: /Chania/ })).toBeInTheDocument()
  })
})
