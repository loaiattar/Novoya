import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { getMeQueryKey } from '../api/generated/@tanstack/react-query.gen'
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

let me: MeResponse
let calls: Call[]
/** What PATCH /me answers. By default, the stored user with the body applied. */
let patchAnswer: ((body: Record<string, string>) => Response | Promise<Response>) | undefined

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    const text = ['POST', 'PATCH'].includes(request.method) ? await request.text() : ''
    const body = text ? JSON.parse(text) : undefined
    calls.push({ method: request.method, path, body })
    if (path === '/me' && request.method === 'PATCH') {
      if (patchAnswer) return patchAnswer(body)
      me = { ...me, ...body }
      me.name = [me.first_name, me.last_name].filter(Boolean).join(' ')
      return Response.json(me)
    }
    if (path === '/me/trips' || path === '/me/preferences') return Response.json([])
    if (path === '/me') return Response.json(me)
    if (path.startsWith('/plans') || path.startsWith('/wishes')) return Response.json([])
    return new Response(null, { status: 204 })
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

async function openProfileTab() {
  fireEvent.mouseDown(await screen.findByRole('tab', { name: 'Personal information' }))
  return screen.findByRole('form', { name: 'Personal information' })
}

const patches = () => calls.filter((call) => call.method === 'PATCH' && call.path === '/me')

beforeEach(async () => {
  client.setConfig({ baseUrl: 'http://api.test' })
  me = { ...CAMILLE }
  calls = []
  patchAnswer = undefined
  mockApi()
  await i18n.changeLanguage('en')
})
afterEach(async () => {
  vi.restoreAllMocks()
  localStorage.clear()
  await i18n.changeLanguage('en')
})

describe('the personal information tab on My trips', () => {
  it('shows the signed-in client from GET /me instead of "coming soon"', async () => {
    renderAt('/trips')
    const form = await openProfileTab()

    expect(within(form).getByLabelText('First name')).toHaveValue('Camille')
    expect(within(form).getByLabelText('Last name')).toHaveValue('Durand')
    expect(within(form).getByLabelText('E-mail')).toHaveValue('camille@exemple.fr')
    expect(within(form).getByLabelText('Language')).toHaveValue('en')
    expect(screen.queryByText(/Coming soon: your personal information/)).not.toBeInTheDocument()
  })

  it('shows the email but does not let it be changed', async () => {
    renderAt('/trips')
    const form = await openProfileTab()

    const email = within(form).getByLabelText('E-mail')
    expect(email).toHaveAttribute('readonly')
    expect(email).toHaveAccessibleDescription(/sign in/i)
  })

  it('saves the names and the language, says so, and shows the stored values', async () => {
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('First name'), { target: { value: 'Camille-Anne' } })
    fireEvent.change(within(form).getByLabelText('Last name'), { target: { value: 'Martin' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Your details are saved.')
    expect(patches()).toEqual([
      { method: 'PATCH', path: '/me', body: { first_name: 'Camille-Anne', last_name: 'Martin' } },
    ])
    // Everything that shows the user follows: the header too.
    // The header names the client by their first name.
    await waitFor(() => expect(within(screen.getByRole('banner')).getByText('Camille-Anne')).toBeInTheDocument())
    expect(within(form).getByLabelText('First name')).toHaveValue('Camille-Anne')
    expect(within(form).getByLabelText('Last name')).toHaveValue('Martin')
  })

  it('shows the values the API stored, not only what was typed', async () => {
    patchAnswer = () => {
      me = { ...me, first_name: 'Camille', last_name: 'Martin', name: 'Camille Martin' }
      return Response.json(me)
    }
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('Last name'), { target: { value: '  Martin  ' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    await screen.findByRole('status')
    expect(within(form).getByLabelText('Last name')).toHaveValue('Martin')
  })

  it('shows a name error next to its field', async () => {
    patchAnswer = () =>
      Response.json(
        { code: 'invalid_input', detail: 'first_name: String should have at least 1 character' },
        { status: 422 },
      )
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('First name'), { target: { value: ' ' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(within(form).getByLabelText('First name')).toHaveAccessibleDescription('Enter your first name.'),
    )
    expect(within(form).getByLabelText('First name')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('sends one PATCH for a double submit before the page renders again', async () => {
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('First name'), { target: { value: 'Camille-Anne' } })
    fireEvent.submit(form)
    fireEvent.submit(form)
    expect(await screen.findByRole('status')).toHaveTextContent('Your details are saved.')

    expect(patches()).toEqual([{ method: 'PATCH', path: '/me', body: { first_name: 'Camille-Anne' } }])
  })

  it('sends one PATCH for a double tap on Save', async () => {
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('First name'), { target: { value: 'Camille-Anne' } })
    const button = within(form).getByRole('button', { name: 'Save' })
    fireEvent.click(button)
    fireEvent.click(button)
    expect(await screen.findByRole('status')).toHaveTextContent('Your details are saved.')

    expect(patches()).toHaveLength(1)
  })

  it('disables the button and says it is saving while the PATCH is on its way', async () => {
    let answer: (response: Response) => void = () => {}
    patchAnswer = (body) =>
      new Promise((resolve) => {
        answer = resolve
        me = { ...me, ...body }
      })
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('First name'), { target: { value: 'Camille-Anne' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    const busy = await within(form).findByRole('button', { name: 'Saving…' })
    expect(busy).toBeDisabled()
    answer(Response.json(me))
    expect(await screen.findByRole('status')).toHaveTextContent('Your details are saved.')
    expect(within(form).getByRole('button', { name: 'Save' })).toBeEnabled()
  })

  it('saves again after a failed save', async () => {
    let first = true
    patchAnswer = (body) => {
      if (first) {
        first = false
        return Response.json({ code: 'boom', detail: 'boom' }, { status: 500 })
      }
      me = { ...me, ...body }
      return Response.json(me)
    }
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('Last name'), { target: { value: 'Martin' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await within(form).findByRole('alert')).toBeInTheDocument()
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Your details are saved.')
    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
    expect(patches()).toHaveLength(2)
    expect(me.last_name).toBe('Martin')
  })

  it('waits for a header language change before saving the form', async () => {
    let answer: () => void = () => {}
    patchAnswer = (body) => {
      // The header's PATCH is held; any later one answers at once.
      me = { ...me, ...body }
      if (patches().length > 1) return Response.json(me)
      return new Promise((resolve) => {
        answer = () => resolve(Response.json(me))
      })
    }
    renderAt('/trips')
    const form = await openProfileTab()
    fireEvent.change(within(form).getByLabelText('First name'), { target: { value: 'Camille-Anne' } })

    fireEvent.click(screen.getAllByRole('button', { name: 'FR, Français' })[0]!)
    await waitFor(() => expect(patches()).toHaveLength(1))
    await waitFor(() => expect(within(form).getByRole('button', { name: 'Saving…' })).toBeDisabled())
    fireEvent.submit(form)
    expect(patches()).toHaveLength(1)

    answer()
    expect(await screen.findByRole('heading', { name: 'Mes voyages' })).toBeInTheDocument()
    // The submit made while the header saved has settled by now, and sent nothing.
    expect(patches()).toHaveLength(1)
    const french = screen.getByRole('form', { name: 'Informations personnelles' })
    fireEvent.click(await within(french).findByRole('button', { name: 'Enregistrer' }))
    await screen.findByRole('status')

    expect(patches().map((call) => call.body)).toEqual([{ locale: 'fr' }, { first_name: 'Camille-Anne' }])
    expect(me.locale).toBe('fr')
    expect(i18n.language).toBe('fr')
  })

  it('holds the header language switch while the form saves', async () => {
    let answer: () => void = () => {}
    patchAnswer = (body) =>
      new Promise((resolve) => {
        me = { ...me, ...body }
        answer = () => resolve(Response.json(me))
      })
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('First name'), { target: { value: 'Camille-Anne' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patches()).toHaveLength(1))

    const french = screen.getAllByRole('button', { name: 'FR, Français' })[0]!
    await waitFor(() => expect(french).toBeDisabled())
    fireEvent.click(french)
    answer()
    await screen.findByRole('status')

    expect(patches()).toHaveLength(1)
    expect(me.locale).toBe('en')
    expect(i18n.language).toBe('en')
  })

  it('sends nothing when nothing changed, and says the details are saved', async () => {
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Your details are saved.')

    expect(patches()).toEqual([])
  })

  it('sends no name that differs from the stored one only by spaces', async () => {
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('Last name'), { target: { value: ' Durand ' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Your details are saved.')

    expect(patches()).toEqual([])
  })

  it('does not send spaces as a last name that was never stored', async () => {
    me = { ...CAMILLE, last_name: null, name: 'Camille' }
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('Last name'), { target: { value: '   ' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Your details are saved.')

    expect(patches()).toEqual([])
  })

  it('clears a field error once the value is back to the stored one', async () => {
    patchAnswer = () =>
      Response.json({ code: 'invalid_input', detail: 'last_name: String should have at least 1 character' }, { status: 422 })
    renderAt('/trips')
    const form = await openProfileTab()
    const last = within(form).getByLabelText('Last name')

    fireEvent.change(last, { target: { value: '' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(last).toHaveAccessibleDescription('Enter your last name.'))

    fireEvent.change(last, { target: { value: 'Durand' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Your details are saved.')
    expect(last).not.toHaveAttribute('aria-invalid')
    expect(last).not.toHaveAccessibleDescription('Enter your last name.')
    expect(patches()).toHaveLength(1)
  })

  it('clears another failure once nothing is left to save', async () => {
    patchAnswer = () => Response.json({ code: 'boom', detail: 'boom' }, { status: 500 })
    renderAt('/trips')
    const form = await openProfileTab()
    const last = within(form).getByLabelText('Last name')

    fireEvent.change(last, { target: { value: 'Martin' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await within(form).findByRole('alert')).toBeInTheDocument()

    fireEvent.change(last, { target: { value: 'Durand' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Your details are saved.')
    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
    expect(patches()).toHaveLength(1)
  })

  it('shows another failure above the button', async () => {
    patchAnswer = () => Response.json({ code: 'boom', detail: 'boom' }, { status: 500 })
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('Last name'), { target: { value: 'Martin' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    expect(await within(form).findByRole('alert')).toHaveTextContent('Something went wrong. Please try again in a moment.')
  })

  it('does not undo a language chosen in the header since the form was touched', async () => {
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('First name'), { target: { value: 'Camille-Anne' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'FR, Français' })[0]!)
    expect(await screen.findByRole('heading', { name: 'Mes voyages' })).toBeInTheDocument()

    const french = screen.getByRole('form', { name: 'Informations personnelles' })
    expect(within(french).getByLabelText('Langue')).toHaveValue('fr')
    expect(within(french).getByLabelText('Prénom')).toHaveValue('Camille-Anne')
    fireEvent.click(within(french).getByRole('button', { name: 'Enregistrer' }))

    await screen.findByRole('status')
    expect(patches().at(-1)?.body).toEqual({ first_name: 'Camille-Anne' })
    expect(me.locale).toBe('fr')
  })

  it('lets a client without a stored last name save without one', async () => {
    me = { ...CAMILLE, last_name: null, name: 'Camille' }
    renderAt('/trips')
    const form = await openProfileTab()

    const last = within(form).getByLabelText('Last name')
    expect(last).toHaveValue('')
    expect(last).not.toBeRequired()
    expect(within(form).getByLabelText('First name')).toBeRequired()
    fireEvent.change(within(form).getByLabelText('First name'), { target: { value: 'Camille-Anne' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    await screen.findByRole('status')
    expect(patches()).toEqual([{ method: 'PATCH', path: '/me', body: { first_name: 'Camille-Anne' } }])
  })

  it('sends a cleared last name, and shows the error next to it', async () => {
    patchAnswer = () =>
      Response.json({ code: 'invalid_input', detail: 'last_name: String should have at least 1 character' }, { status: 422 })
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('Last name'), { target: { value: '' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(within(form).getByLabelText('Last name')).toHaveAccessibleDescription('Enter your last name.'),
    )
    expect(patches()[0]?.body).toEqual({ last_name: '' })
  })

  it('stops saying "saved" once the client edits again', async () => {
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('First name'), { target: { value: 'Camille-Anne' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Your details are saved.')

    fireEvent.change(within(form).getByLabelText('Last name'), { target: { value: 'Martin' } })
    expect(screen.queryByText('Your details are saved.')).not.toBeInTheDocument()
  })

  it('keeps the typed edits when the idle check drops the cached /me', async () => {
    const { queryClient } = renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('First name'), { target: { value: 'Camille-Anne' } })
    queryClient.removeQueries({ queryKey: getMeQueryKey() })
    fireEvent.change(within(form).getByLabelText('Last name'), { target: { value: 'Martin' } })
    // The tab renders again for another reason (here the interface language).
    await act(() => i18n.changeLanguage('fr'))

    const still = await screen.findByRole('form', { name: 'Informations personnelles' })
    expect(within(still).getByLabelText('Prénom')).toHaveValue('Camille-Anne')
    expect(within(still).getByLabelText('Nom de famille')).toHaveValue('Martin')
  })

  it('switches the interface to the saved language', async () => {
    renderAt('/trips')
    const form = await openProfileTab()

    fireEvent.change(within(form).getByLabelText('Language'), { target: { value: 'fr' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('heading', { name: 'Mes voyages' })).toBeInTheDocument()
    expect(patches()[0]?.body).toEqual({ locale: 'fr' })
    expect(await screen.findByRole('status')).toHaveTextContent('Vos informations sont enregistrées.')
    expect(screen.getByRole('form', { name: 'Informations personnelles' })).toBeInTheDocument()
  })
})
