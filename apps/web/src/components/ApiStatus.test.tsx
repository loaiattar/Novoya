import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { client } from '../api/generated/client.gen'
import { ApiStatus } from './ApiStatus'

function renderWithQuery() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiStatus />
    </QueryClientProvider>,
  )
}

describe('ApiStatus', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows ok when the API and database answer', async () => {
    client.setConfig({ baseUrl: 'http://api.test' })
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => Response.json({ status: 'ok' }))

    renderWithQuery()

    expect(await screen.findByText('API: ok')).toBeInTheDocument()
    expect(await screen.findByText('Database: ok')).toBeInTheDocument()
  })

  it('shows unreachable when the database check fails', async () => {
    client.setConfig({ baseUrl: 'http://api.test' })
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = input instanceof Request ? input.url : String(input)
      return url.endsWith('/health/db')
        ? Response.json({ status: 'error' }, { status: 503 })
        : Response.json({ status: 'ok' })
    })

    renderWithQuery()

    expect(await screen.findByText('Database: unreachable')).toBeInTheDocument()
  })
})
