import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../api/client'
import { client } from '../api/generated/client.gen'
import type { MeResponse, UserResponse } from '../api/generated/types.gen'
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

const NEW_USER: UserResponse = {
  id: '6f1c2b1e-0000-4000-8000-000000000004',
  email: 'camille@exemple.fr',
  name: 'Camille Durand',
  first_name: 'Camille',
  last_name: 'Durand',
  role: 'client',
  locale: 'en',
  status: 'active',
  status_changed_by: null,
  status_changed_at: null,
  email_verified: false,
  created_at: '2026-10-20T10:00:00Z',
}

type Call = { method: string; path: string; body: unknown }

let signedIn: MeResponse | null
let calls: Call[]
/** What the API answers, by path. A path missing here answers 204. */
let answers: Record<string, () => Response>

const error = (status: number, code: string, detail = code) => () =>
  Response.json({ code, detail }, { status })

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const path = new URL(request.url).pathname
    const text = request.method === 'POST' ? await request.text() : ''
    calls.push({ method: request.method, path, body: text ? JSON.parse(text) : undefined })
    if (path === '/me') {
      return signedIn
        ? Response.json(signedIn)
        : Response.json({ code: 'unauthenticated', detail: 'not signed in' }, { status: 401 })
    }
    return answers[path]?.() ?? new Response(null, { status: 204 })
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

const posts = (path: string) => calls.filter((call) => call.method === 'POST' && call.path === path)
const browserLanguages = (languages: string[]) => vi.spyOn(navigator, 'languages', 'get').mockReturnValue(languages)

async function type(label: string, value: string) {
  fireEvent.change(await screen.findByLabelText(label), { target: { value } })
}

beforeEach(() => {
  client.setConfig({ baseUrl: 'http://api.test' })
  signedIn = null
  calls = []
  answers = {
    '/auth/register': () => Response.json(NEW_USER, { status: 201 }),
    '/auth/email/verify/resend': () => new Response(null, { status: 202 }),
    '/auth/password/forgot': () => new Response(null, { status: 202 }),
  }
  mockApi()
})
afterEach(() => {
  vi.restoreAllMocks()
})

describe('the sign-in page', () => {
  it('links to the lost password and sign-up pages', async () => {
    renderAt('/login')

    expect(await screen.findByRole('link', { name: 'Forgot password?' })).toHaveAttribute('href', '/forgot-password')
    expect(screen.getByRole('link', { name: 'Sign up' })).toHaveAttribute('href', '/signup')
  })
})

describe('signing up', () => {
  async function fillAndSend(
    email: string,
    password: string,
    labels = { first: 'First name', last: 'Last name', email: 'E-mail', password: 'Password' },
  ) {
    await type(labels.first, 'Camille')
    await type(labels.last, 'Durand')
    await type(labels.email, email)
    await type(labels.password, password)
    fireEvent.click(screen.getByRole('button', { name: /^(Create my account|Créer mon compte)/ }))
  }

  it('offers Google too', async () => {
    renderAt('/signup')

    expect(await screen.findByRole('link', { name: 'Continue with Google' })).toHaveAttribute(
      'href',
      'http://api.test/auth/google/login?redirect_to=%2Fwish',
    )
  })

  it('creates the account, then asks to check the e-mail', async () => {
    renderAt('/signup')

    await fillAndSend(' camille@exemple.fr ', 'a long enough password')

    expect(await screen.findByRole('heading', { name: 'Check your e-mail' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('We sent a link to camille@exemple.fr.')
    expect(posts('/auth/register')[0]!.body).toEqual({
      first_name: 'Camille',
      last_name: 'Durand',
      email: 'camille@exemple.fr',
      password: 'a long enough password',
      locale: 'en',
    })
  })

  it('asks for a first name and a last name, required, with the right autocomplete', async () => {
    renderAt('/signup')

    const first = await screen.findByLabelText('First name')
    const last = screen.getByLabelText('Last name')
    expect(first).toBeRequired()
    expect(last).toBeRequired()
    expect(first).toHaveAttribute('autocomplete', 'given-name')
    expect(last).toHaveAttribute('autocomplete', 'family-name')
    expect(first).toHaveAttribute('placeholder', 'Your first name')
    expect(last).toHaveAttribute('placeholder', 'Your last name')
  })

  it('shows the name fields in French', async () => {
    browserLanguages(['fr-FR'])
    renderAt('/signup')

    const first = await screen.findByLabelText('Prénom')
    const last = screen.getByLabelText('Nom de famille')
    expect(first).toHaveAttribute('placeholder', 'Votre prénom')
    expect(last).toHaveAttribute('placeholder', 'Votre nom')
  })

  it('shows a missing first name next to its field', async () => {
    answers['/auth/register'] = error(422, 'invalid_input', 'first_name: Field required')
    renderAt('/signup')

    await fillAndSend('camille@exemple.fr', 'a long enough password')

    const first = screen.getByLabelText('First name')
    await waitFor(() => expect(first).toHaveAccessibleDescription('Enter your first name.'))
    expect(first).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Last name')).not.toHaveAttribute('aria-invalid')
  })

  it('says so next to the e-mail when it already has an account', async () => {
    answers['/auth/register'] = error(409, 'email_already_used')
    renderAt('/signup')

    await fillAndSend('camille@exemple.fr', 'a long enough password')

    const email = screen.getByLabelText('E-mail')
    await waitFor(() => expect(email).toHaveAccessibleDescription('This e-mail already has an account. Sign in, or reset your password.'))
    expect(email).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('heading', { name: 'Create an account' })).toBeInTheDocument()
  })

  it('shows a weak password error next to the password, under its hint', async () => {
    answers['/auth/register'] = error(422, 'weak_password')
    renderAt('/signup')

    await fillAndSend('camille@exemple.fr', 'short')

    const password = screen.getByLabelText('Password')
    await waitFor(() => expect(password).toHaveAccessibleDescription(/^At least 12 characters\. Choose a stronger password/))
    expect(password).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('E-mail')).not.toHaveAttribute('aria-invalid')
  })

  it('shows the errors in French, and creates the account in French', async () => {
    browserLanguages(['fr-FR'])
    answers['/auth/register'] = error(422, 'invalid_email')
    renderAt('/signup')

    await fillAndSend('camille@exemple', 'a long enough password', {
      first: 'Prénom',
      last: 'Nom de famille',
      email: 'E-mail',
      password: 'Mot de passe',
    })

    await waitFor(() =>
      expect(screen.getByLabelText('E-mail')).toHaveAccessibleDescription('Cette adresse e-mail ne semble pas valide.'),
    )
    expect(posts('/auth/register')[0]!.body).toMatchObject({ locale: 'fr' })
  })

  it('shows a weak password error in French', async () => {
    browserLanguages(['fr-FR'])
    answers['/auth/register'] = error(422, 'weak_password')
    renderAt('/signup')

    await fillAndSend('camille@exemple.fr', 'court', {
      first: 'Prénom',
      last: 'Nom de famille',
      email: 'E-mail',
      password: 'Mot de passe',
    })

    await waitFor(() =>
      expect(screen.getByLabelText('Mot de passe')).toHaveAccessibleDescription(
        /Choisissez un mot de passe plus solide/,
      ),
    )
  })

  it('sends a signed-in user to their space', async () => {
    signedIn = CAMILLE
    const { router } = renderAt('/signup')

    expect(await screen.findByRole('heading', { name: /What would you/ })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/wish')
  })
})

describe('confirming the e-mail', () => {
  it('sends the token of the link once and says the e-mail is confirmed', async () => {
    renderAt('/verify-email?token=abc123')

    expect(await screen.findByRole('heading', { name: 'Your e-mail is confirmed' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
    expect(posts('/auth/email/verify')).toEqual([{ method: 'POST', path: '/auth/email/verify', body: { token: 'abc123' } }])
  })

  it('says the link expired and sends a new one', async () => {
    answers['/auth/email/verify'] = error(422, 'invalid_token')
    renderAt('/verify-email?token=used')

    expect(await screen.findByRole('heading', { name: 'This link has expired' })).toBeInTheDocument()
    await type('E-mail', 'camille@exemple.fr')
    fireEvent.click(screen.getByRole('button', { name: 'Send a new link' }))

    expect(await screen.findByRole('status')).toHaveTextContent('a new link is on its way')
    expect(posts('/auth/email/verify/resend')[0]!.body).toEqual({ email: 'camille@exemple.fr' })
  })

  it('treats a link without a token as expired, without asking the API', async () => {
    renderAt('/verify-email')

    expect(await screen.findByRole('heading', { name: 'This link has expired' })).toBeInTheDocument()
    expect(posts('/auth/email/verify')).toEqual([])
  })

  it('offers to try again when the API cannot be reached', async () => {
    answers['/auth/email/verify'] = error(500, 'internal_error')
    renderAt('/verify-email?token=abc123')

    expect(await screen.findByRole('alert')).toHaveTextContent("can't reach the server")
    answers['/auth/email/verify'] = () => new Response(null, { status: 204 })
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { name: 'Your e-mail is confirmed' })).toBeInTheDocument()
  })
})

describe('the forgotten password', () => {
  it('always gives the same answer', async () => {
    renderAt('/forgot-password')

    await type('E-mail', 'nobody@exemple.fr')
    fireEvent.click(screen.getByRole('button', { name: 'Send the link' }))

    expect(await screen.findByRole('heading', { name: 'Check your e-mail' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('If an account uses this address')
    expect(posts('/auth/password/forgot')[0]!.body).toEqual({ email: 'nobody@exemple.fr' })
  })
})

describe('choosing a new password', () => {
  it('saves it and goes to the sign-in page', async () => {
    const { router } = renderAt('/reset-password?token=reset123')

    await type('New password', 'a brand new password')
    fireEvent.click(screen.getByRole('button', { name: 'Save the password' }))

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Your password is changed.')
    expect(router.state.location.pathname).toBe('/login')
    expect(posts('/auth/password/reset')[0]!.body).toEqual({ token: 'reset123', new_password: 'a brand new password' })
  })

  it('shows a weak password error next to the field and stays', async () => {
    answers['/auth/password/reset'] = error(422, 'weak_password')
    const { router } = renderAt('/reset-password?token=reset123')

    await type('New password', 'short')
    fireEvent.click(screen.getByRole('button', { name: 'Save the password' }))

    await waitFor(() =>
      expect(screen.getByLabelText('New password')).toHaveAccessibleDescription(/Choose a stronger password/),
    )
    expect(router.state.location.pathname).toBe('/reset-password')
  })

  it('says when the link expired, and offers a new one', async () => {
    answers['/auth/password/reset'] = error(422, 'invalid_token')
    renderAt('/reset-password?token=old')

    await type('New password', 'a brand new password')
    fireEvent.click(screen.getByRole('button', { name: 'Save the password' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('This link has expired or was already used.')
    expect(screen.getByRole('link', { name: 'Ask for a new link' })).toHaveAttribute('href', '/forgot-password')
  })

  it('treats a link without a token as expired', async () => {
    renderAt('/reset-password')

    expect(await screen.findByRole('alert')).toHaveTextContent('This link has expired')
    expect(screen.queryByLabelText('New password')).not.toBeInTheDocument()
  })
})

describe('changing the password in the account settings', () => {
  async function fillAndSend(current: string, next: string) {
    await type('Current password', current)
    await type('New password', next)
    fireEvent.click(screen.getByRole('button', { name: 'Change the password' }))
  }

  it('is in the account menu', async () => {
    signedIn = CAMILLE
    renderAt('/wish')

    // The account menu is a Radix dropdown: it opens on pointer down, not on click.
    fireEvent.pointerDown(await screen.findByRole('button', { name: /Camille/ }), { button: 0, ctrlKey: false })

    expect(await screen.findByRole('menuitem', { name: 'Account settings' })).toHaveAttribute('href', '/settings')
  })

  it('changes it and empties the form', async () => {
    signedIn = CAMILLE
    renderAt('/settings')

    await fillAndSend('my old password', 'a brand new password')

    expect(await screen.findByRole('status')).toHaveTextContent('Your password is changed.')
    expect(screen.getByLabelText('Current password')).toHaveValue('')
    expect(posts('/auth/password/change')[0]!.body).toEqual({
      current_password: 'my old password',
      new_password: 'a brand new password',
    })
  })

  it('says so next to the current password when it is wrong', async () => {
    signedIn = CAMILLE
    answers['/auth/password/change'] = error(401, 'invalid_credentials')
    renderAt('/settings')

    await fillAndSend('not my password', 'a brand new password')

    const current = screen.getByLabelText('Current password')
    await waitFor(() => expect(current).toHaveAccessibleDescription('Your current password is wrong.'))
    expect(current).toHaveValue('not my password')
  })

  it('has no password to change for a Google account', async () => {
    signedIn = { ...CAMILLE, sign_in_methods: ['google'] }
    renderAt('/settings')

    expect(await screen.findByText(/You sign in with Google/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Current password')).not.toBeInTheDocument()
  })
})
