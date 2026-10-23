import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../../api/client'
import { getMeQueryKey } from '../../api/generated/@tanstack/react-query.gen'
import { client } from '../../api/generated/client.gen'
import type { MeResponse } from '../../api/generated/types.gen'
import i18n from '../../i18n'
import { useLanguageChoice } from './useLanguageChoice'
import { useUpdateMe } from './useUpdateMe'

// The hooks reload the signed-in layout after a save; no router is needed to test them.
vi.mock('@tanstack/react-router', () => ({ useRouter: () => ({ invalidate: async () => {} }) }))

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

let patches: unknown[]

beforeEach(async () => {
  client.setConfig({ baseUrl: 'http://api.test' })
  patches = []
  // Every PATCH /me stays on its way.
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    if (request.method === 'PATCH') {
      patches.push(JSON.parse(await request.text()))
      return new Promise<Response>(() => {})
    }
    return Response.json(CAMILLE)
  })
  await i18n.changeLanguage('en')
})
afterEach(async () => {
  vi.restoreAllMocks()
  localStorage.clear()
  await i18n.changeLanguage('en')
})

describe('useLanguageChoice', () => {
  it('sends nothing while another PATCH /me is on its way', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    queryClient.setQueryData(getMeQueryKey(), CAMILLE)
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => ({ choice: useLanguageChoice(), profile: useUpdateMe() }), { wrapper })

    act(() => result.current.profile.mutate({ body: { first_name: 'Camille-Anne' } }))
    await waitFor(() => expect(result.current.choice.saving).toBe(true))
    await waitFor(() => expect(patches).toHaveLength(1))

    act(() => result.current.choice.choose('fr'))
    // Without the guard, choose() adds a second mutation at once.
    expect(queryClient.getMutationCache().getAll()).toHaveLength(1)
    await act(async () => {})
    expect(patches).toEqual([{ first_name: 'Camille-Anne' }])
    expect(i18n.language).toBe('en')
  })
})
