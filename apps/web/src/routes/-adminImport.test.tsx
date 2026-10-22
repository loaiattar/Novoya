import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse } from '../api/generated/types.gen'
import { createAppRouter } from '../router'

const ADMIN: MeResponse = {
  id: '00000000-0000-4000-8000-000000000001',
  email: 'nadia@example.test',
  name: 'Nadia Ferhat',
  first_name: 'Nadia',
  last_name: 'Ferhat',
  role: 'admin',
  locale: 'en',
  status: 'active',
  email_verified: true,
  created_at: '2026-08-18T10:00:00Z',
  sign_in_methods: ['password'],
}

const COUNTS = { partners: 396, offers: 792, reviews: 54, extras: 104 }

let me: MeResponse
let importAnswer: () => Response | Promise<Response>
let requests: { method: string; path: string; type: string | null; size: number }[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    const size = request.method === 'GET' ? 0 : (await request.clone().arrayBuffer()).byteLength
    requests.push({ method: request.method, path: url.pathname, type: request.headers.get('Content-Type'), size })
    if (url.pathname === '/me') return Response.json(me)
    if (url.pathname === '/admin/catalog/import' && request.method === 'POST') return importAnswer()
    return Response.json({ code: 'not_found', detail: 'no route' }, { status: 404 })
  })
}

const imports = () => requests.filter((request) => request.path === '/admin/catalog/import')

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

function exportFile(name = 'detour.sqlite', bytes = 'SQLite format 3\0made up') {
  return new File([bytes], name, { type: 'application/octet-stream' })
}

async function choose(file: File, label = /export \(\.sqlite\)/) {
  const input = await screen.findByLabelText(label, {}, { timeout: 3000 })
  fireEvent.change(input, { target: { files: [file] } })
}

describe('admin import', () => {
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    me = ADMIN
    importAnswer = () => Response.json(COUNTS)
    requests = []
    mockApi()
  })
  afterEach(() => vi.restoreAllMocks())

  it('imports the chosen export and shows the counts', async () => {
    renderAt('/admin/import')
    const file = exportFile()

    await choose(file)
    fireEvent.click(screen.getByRole('button', { name: 'Import' }))

    const done = await screen.findByRole('status')
    expect(done).toHaveTextContent('Export imported.')
    expect(done).toHaveTextContent('Partners396')
    expect(done).toHaveTextContent('Offers792')
    expect(done).toHaveTextContent('Reviews54')
    expect(done).toHaveTextContent('Extras104')
    expect(imports()).toEqual([
      { method: 'POST', path: '/admin/catalog/import', type: 'application/octet-stream', size: file.size },
    ])
    expect(screen.getByRole('link', { name: 'Import' })).toHaveAttribute('aria-current', 'page')
  })

  it('refuses a file that is not a .sqlite export without sending it', async () => {
    renderAt('/admin/import')

    await choose(exportFile('detour.xlsx'))

    expect(await screen.findByText('This is not a DÉTOUR export: choose the .sqlite file.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Import' })).toBeDisabled()
    expect(imports()).toHaveLength(0)
  })

  it('refuses a file over the size limit without sending it', async () => {
    renderAt('/admin/import')
    const big = exportFile()
    Object.defineProperty(big, 'size', { value: 20_000_001 })

    await choose(big)

    expect(await screen.findByText('This file is larger than 20 MB.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Import' })).toBeDisabled()
  })

  it.each([
    [
      422,
      'detour_import_failed',
      'offres F099: unknown partner',
      'Nothing was imported: a row of the export was refused (offres F099: unknown partner). Fix it in DÉTOUR, then import a new export.',
    ],
    [422, 'not_a_detour_export', 'not sqlite', 'This is not a DÉTOUR export: choose the .sqlite file.'],
    [409, 'import_running', 'busy', 'Another import is running. Try again in a moment.'],
    [413, 'detour_export_too_large', 'too large', 'This file is larger than 20 MB.'],
    [500, 'unknown', 'boom', 'The export could not be imported. Please try again.'],
  ])('explains a %s %s answer', async (status, code, detail, message) => {
    importAnswer = () => Response.json({ code, detail }, { status })
    renderAt('/admin/import')

    await choose(exportFile())
    fireEvent.click(screen.getByRole('button', { name: 'Import' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it.each(['client', 'agent'] as const)('sends someone with the %s role away', async (role) => {
    me = { ...ADMIN, role }
    const { router } = renderAt('/admin/import')

    await waitFor(() => expect(router.state.location.pathname).toBe('/wish'))
    expect(imports()).toHaveLength(0)
  })

  it("shows the page in the admin's language", async () => {
    me = { ...ADMIN, locale: 'fr' }
    renderAt('/admin/import')

    expect(await screen.findByRole('heading', { level: 1, name: 'Importer un export' }, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.getByLabelText('Export DÉTOUR (.sqlite)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Importer' })).toBeDisabled()
    expect(screen.getByRole('link', { name: 'Import' })).toBeInTheDocument()
  })
})
