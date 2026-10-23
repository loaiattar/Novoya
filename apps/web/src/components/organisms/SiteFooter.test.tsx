import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRootRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../../i18n'
import { SiteFooter } from './SiteFooter'

beforeEach(async () => {
  await i18n.changeLanguage('en')
})

afterEach(() => vi.restoreAllMocks())

async function renderFooter() {
  const rootRoute = createRootRoute({ component: SiteFooter })
  const router = createRouter({ routeTree: rootRoute, history: createMemoryHistory({ initialEntries: ['/'] }) })
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return screen.findByRole('contentinfo')
}

describe('SiteFooter', () => {
  it('lists the links in two columns, each one under the other', async () => {
    const footer = await renderFooter()
    const nav = within(footer).getByRole('navigation', { name: 'Footer links' })
    const [first, second] = within(nav).getAllByRole('list')
    expect(within(first).getAllByRole('link').map((a) => a.textContent)).toEqual([
      'Destinations',
      'About us',
      'Privacy policy',
    ])
    expect(within(second).getAllByRole('link').map((a) => a.textContent)).toEqual([
      'Surprise weekends',
      'Contact',
      'Legal notices',
    ])
    expect(within(nav).getByRole('link', { name: 'About us' })).toHaveAttribute('href', '/#equipe')
    expect(within(nav).getByRole('link', { name: 'Surprise weekends' })).toHaveAttribute('href', '/#voyages')
  })

  it('says the newsletter is not open yet instead of pretending to sign up', async () => {
    const footer = await renderFooter()
    fireEvent.change(within(footer).getByLabelText('Get a surprise destination every month'), {
      target: { value: 'ana@example.com' },
    })
    fireEvent.click(within(footer).getByRole('button', { name: 'Sign up' }))
    expect(within(footer).getByText(/The newsletter opens soon\./)).toBeInTheDocument()
  })

  it('shows the time in Nantes', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-23T13:30:00Z'))
    const footer = await renderFooter()
    expect(within(footer).getByText('Local time · 15:30')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('takes the reader back to the top', async () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    const footer = await renderFooter()
    fireEvent.click(within(footer).getByRole('button', { name: 'Back to top' }))
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 0 }))
  })
})
