import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import i18n from '../i18n'
import { createAppRouter } from '../router'

let router: ReturnType<typeof createAppRouter> | undefined

// Nobody is signed in: the privacy page is public, like the Google consent screen that links to it.
function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
    Response.json({ code: 'unauthenticated', detail: 'not signed in' }, { status: 401 }),
  )
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

describe('privacy page', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    mockApi()
  })
  afterEach(async () => {
    await waitFor(() => expect(router?.state.status).toBe('idle'))
    await i18n.changeLanguage('en')
    vi.restoreAllMocks()
  })

  it('opens without signing in and covers what we store, why, how long and how to delete it', async () => {
    renderAt('/privacy')

    expect(await screen.findByRole('heading', { level: 1, name: 'Privacy policy' })).toBeInTheDocument()
    for (const heading of [
      'What we store, and why',
      'What we never do',
      'Who else handles it',
      'How long we keep it',
      'Your rights',
    ]) {
      expect(screen.getByRole('heading', { level: 2, name: heading })).toBeInTheDocument()
    }
    const text = document.body.textContent ?? ''
    expect(text).toContain('We never read your mailbox, your documents, your contacts or your social media')
    expect(text).toContain('Never your IP address.')
    expect(text).toContain('A session: 30 days at most.')
    expect(text).toContain('Mistral AI, in France')
    expect(text).toContain('agreed to their publication')
    // The advisor chat (#169): what, who reads it, how long.
    expect(text).toContain('Your messages to our advisors')
    expect(text).toContain("The advisor chat: you, the agency's administrators")
    // The advisors on the home page (#167): shown only with their agreement, no photo.
    expect(screen.getByRole('heading', { level: 2, name: "Our advisors' public profile" })).toBeInTheDocument()
    expect(text).toContain('only once they agreed to it')
    expect(text).toContain('Your chat messages: as long as the trip wish they belong to.')
    expect(text).toContain('12 rue des Écluses, 44000 Nantes')
    expect(screen.getAllByRole('link', { name: '02 40 00 00 00' })[0]).toHaveAttribute('href', 'tel:+33240000000')
    expect(screen.getByRole('link', { name: 'Open my account settings' })).toHaveAttribute('href', '/settings')
    expect(router?.state.location.pathname).toBe('/privacy')
  })

  it('is in French for a French reader', async () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['fr-FR'])
    await i18n.changeLanguage('fr')
    renderAt('/privacy')

    expect(await screen.findByRole('heading', { level: 1, name: 'Politique de confidentialité' })).toBeInTheDocument()
    expect(document.body.textContent).toContain('Nous ne lisons jamais votre messagerie')
    expect(document.body.textContent).toContain('Vos messages à nos conseillers')
    expect(document.body.textContent).toContain('La discussion avec un conseiller : vous, les administrateurs de l’agence')
    expect(document.body.textContent).toContain('Vos messages de discussion : aussi longtemps que l’envie de voyage')
    expect(screen.getByRole('heading', { name: 'Le profil public de nos conseillers' })).toBeInTheDocument()
  })

  it('is linked from the sign-in page', async () => {
    renderAt('/login')

    expect(await screen.findByRole('link', { name: 'privacy policy' })).toHaveAttribute('href', '/privacy')
  })

  it('is linked from the site footer', async () => {
    renderAt('/legal')

    const footer = await screen.findByRole('contentinfo')
    expect(within(footer).getByRole('link', { name: 'Privacy policy' })).toHaveAttribute('href', '/privacy')
  })
})
