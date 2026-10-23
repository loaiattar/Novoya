import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { AgentAdvisorResponse, MeResponse } from '../api/generated/types.gen'
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

// Made-up agents: one without a profile yet, one shown on the home page.
const SAMI: AgentAdvisorResponse = {
  user_id: '00000000-0000-4000-8000-000000000071',
  email: 'sami@example.test',
  name: 'Sami Benali',
  status: 'active',
  profile: null,
}

const CAMILLE: AgentAdvisorResponse = {
  user_id: '00000000-0000-4000-8000-000000000072',
  email: 'camille@example.test',
  name: 'Camille Durand',
  status: 'active',
  profile: {
    public_name: 'Camille',
    title: 'Founder',
    summary: 'Always looking for the next gem.',
    services: [{ fr: 'Grèce', en: 'Greece' }],
    consent: true,
    consent_at: '2026-10-20T09:00:00Z',
    shown: true,
    updated_at: '2026-10-20T09:00:00Z',
  },
}

let saveAnswer: ((body: unknown) => Response) | undefined
let requests: { method: string; path: string; body?: unknown }[]

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    const body = request.method === 'GET' ? undefined : await request.clone().json().catch(() => undefined)
    requests.push({ method: request.method, path: url.pathname, body })
    if (url.pathname === '/me') return Response.json(ADMIN)
    if (url.pathname === '/admin/advisors') return Response.json([SAMI, CAMILLE])
    if (request.method === 'PUT' && saveAnswer) return saveAnswer(body)
    return Response.json({ code: 'not_found', detail: 'no route' }, { status: 404 })
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
  return router
}

const card = async (name: string) =>
  (await screen.findByRole('heading', { level: 2, name })).closest('li') as HTMLElement

describe('admin advisors page', () => {
  let router: ReturnType<typeof createAppRouter> | undefined
  beforeEach(() => {
    client.setConfig({ baseUrl: 'http://api.test' })
    requests = []
    saveAnswer = undefined
    mockApi()
  })
  afterEach(async () => {
    await waitFor(() => expect(router?.state.status).toBe('idle'))
    vi.restoreAllMocks()
  })

  it('lists the agents with what the home page shows of them', async () => {
    router = renderAt('/admin/advisors')

    expect(within(await card('Sami Benali')).getByText('Profile to fill in')).toBeInTheDocument()
    expect(within(await card('Camille')).getByText('Shown on the home page')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Advisors' })).toHaveAttribute('href', '/admin/advisors')
  })

  it('saves a profile with services in one language or both, once the agent agreed', async () => {
    saveAnswer = (body) =>
      Response.json({ ...SAMI, profile: { ...(body as object), consent_at: '2026-10-23T09:00:00Z', updated_at: '2026-10-23T09:00:00Z' } })
    router = renderAt('/admin/advisors')
    const sami = await card('Sami Benali')
    fireEvent.click(within(sami).getByRole('button', { name: 'Edit the profile' }))

    fireEvent.change(within(sami).getByLabelText('Public name'), { target: { value: 'Sami' } })
    fireEvent.change(within(sami).getByLabelText('One-line introduction'), { target: { value: 'Trains first.' } })
    expect(within(sami).getByText('13 / 140 characters.')).toBeInTheDocument()
    fireEvent.click(within(sami).getByRole('button', { name: 'Add a speciality' }))
    fireEvent.change(within(sami).getByLabelText('Speciality 1 in French'), { target: { value: 'Maroc' } })
    fireEvent.click(within(sami).getByRole('button', { name: 'Add a speciality' }))
    fireEvent.change(within(sami).getByLabelText('Speciality 2 in English'), { target: { value: 'Night trains' } })

    // Shown only once the agent agreed.
    const shown = within(sami).getByRole('checkbox', { name: 'Show on the home page' })
    expect(shown).toBeDisabled()
    fireEvent.click(within(sami).getByRole('checkbox', { name: 'The agent agreed to appear on the site' }))
    fireEvent.click(shown)
    fireEvent.click(within(sami).getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Profile saved.')
    const [put] = requests.filter((r) => r.method === 'PUT')
    expect(put?.path).toBe(`/admin/advisors/${SAMI.user_id}`)
    expect(put?.body).toEqual({
      public_name: 'Sami',
      title: null,
      summary: 'Trains first.',
      services: [
        { fr: 'Maroc', en: null },
        { fr: null, en: 'Night trains' },
      ],
      consent: true,
      shown: true,
    })
  })

  it('refuses a speciality with neither French nor English, and sends nothing', async () => {
    router = renderAt('/admin/advisors')
    const sami = await card('Sami Benali')
    fireEvent.click(within(sami).getByRole('button', { name: 'Edit the profile' }))
    fireEvent.click(within(sami).getByRole('button', { name: 'Add a speciality' }))
    fireEvent.click(within(sami).getByRole('button', { name: 'Save' }))

    expect(
      await within(sami).findByText('Write this speciality in French or in English, or remove it.'),
    ).toBeInTheDocument()
    expect(within(sami).getByLabelText('Speciality 1 in French')).toHaveAttribute('aria-invalid', 'true')
    expect(requests.filter((r) => r.method === 'PUT')).toEqual([])
  })

  it('unticking the agreement hides the profile', async () => {
    router = renderAt('/admin/advisors')
    const camille = await card('Camille')
    fireEvent.click(within(camille).getByRole('button', { name: 'Edit the profile' }))
    const shown = within(camille).getByRole('checkbox', { name: 'Show on the home page' })
    expect(shown).toBeChecked()

    fireEvent.click(within(camille).getByRole('checkbox', { name: 'The agent agreed to appear on the site' }))

    expect(shown).not.toBeChecked()
    expect(shown).toBeDisabled()
  })

  it('says why the API refused the save', async () => {
    saveAnswer = () => Response.json({ code: 'not_an_agent', detail: 'no longer an agent' }, { status: 409 })
    router = renderAt('/admin/advisors')
    const camille = await card('Camille')
    fireEvent.click(within(camille).getByRole('button', { name: 'Edit the profile' }))
    fireEvent.click(within(camille).getByRole('button', { name: 'Save' }))

    expect(await within(camille).findByRole('alert')).toHaveTextContent('This user is no longer an agent')
  })
})
