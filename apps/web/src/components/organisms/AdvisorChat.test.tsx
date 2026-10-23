import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import '../../api/client'
import { client } from '../../api/generated/client.gen'
import type { ChatMessage } from '../../api/generated/types.gen'
import { AdvisorChat, ChatThread } from './AdvisorChat'

const WISH_ID = '00000000-0000-4000-8000-0000000000a1'
const PATH = `/wishes/${WISH_ID}/messages`

let stored: ChatMessage[]
let posted: unknown[]

function wrap(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>)
}

beforeEach(() => {
  client.setConfig({ baseUrl: 'http://api.test' })
  stored = [
    { id: '1', body: 'Can we add a day in Kyoto?', from_agency: false, mine: true, sent_at: '2026-10-23T09:00:00Z' },
  ]
  posted = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)
    if (url.pathname === PATH && request.method === 'GET') return Response.json(stored)
    if (url.pathname === PATH && request.method === 'POST') {
      const body = (await request.json()) as { body: string }
      posted.push(body)
      const message = { id: String(stored.length + 1), body: body.body, from_agency: false, mine: true, sent_at: '2026-10-23T09:05:00Z' }
      stored = [...stored, message]
      return Response.json(message, { status: 201 })
    }
    return Response.json({ code: 'not_found', detail: 'no route' }, { status: 404 })
  })
})

afterEach(() => vi.restoreAllMocks())

describe('AdvisorChat', () => {
  it('opens a labelled dialog from the button, focuses the message box and closes on Escape', async () => {
    wrap(<AdvisorChat wishId={WISH_ID} />)
    const opener = screen.getByRole('button', { name: 'Chat with an advisor' })
    expect(opener).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    fireEvent.click(opener)

    const dialog = screen.getByRole('dialog', { name: 'Your advisor' })
    expect(opener).toHaveAttribute('aria-expanded', 'true')
    expect(within(dialog).getByLabelText('Your message')).toHaveFocus()
    expect(await within(dialog).findByText('Can we add a day in Kyoto?')).toBeInTheDocument()

    fireEvent.keyDown(dialog, { key: 'Escape' })

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })

  it('does not read the conversation while closed', () => {
    wrap(<AdvisorChat wishId={WISH_ID} />)
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })
})

describe('ChatThread', () => {
  it('sends a message and shows it in the conversation log', async () => {
    wrap(<ChatThread wishId={WISH_ID} side="client" />)
    const log = screen.getByRole('log', { name: 'Messages' })
    await within(log).findByText('Can we add a day in Kyoto?')

    fireEvent.change(screen.getByLabelText('Your message'), { target: { value: 'And a ryokan?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await within(log).findByText('And a ryokan?')).toBeInTheDocument()
    expect(posted).toEqual([{ body: 'And a ryokan?' }])
    expect(screen.getByLabelText('Your message')).toHaveValue('')
  })

  it('does not send an empty message', () => {
    wrap(<ChatThread wishId={WISH_ID} side="client" />)
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
  })

  it('names the client on the agent side', async () => {
    stored = [{ ...stored[0], mine: false }]
    wrap(<ChatThread wishId={WISH_ID} side="agency" />)
    const log = screen.getByRole('log', { name: 'Messages' })
    expect(await within(log).findByText('Client')).toBeInTheDocument()
    await waitFor(() => expect(within(log).getByText('Can we add a day in Kyoto?')).toBeInTheDocument())
  })
})
