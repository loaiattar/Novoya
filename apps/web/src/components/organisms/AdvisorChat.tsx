import { MessageCircle, X } from 'lucide-react'
import { type FormEvent, type KeyboardEvent, useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ChatMessage } from '../../api/generated/types.gen'
import { usePostMessage, useWishMessages } from '../../api/messages'
import { Button } from '../atoms/Button'

const MAX_LENGTH = 2000

type Side = 'client' | 'agency'

/**
 * The advisor chat while the client composes a trip (#169): a button at the bottom right
 * opens a small, non-modal dialog. On a phone it takes the bottom of the screen and closes
 * with its button or Escape; focus goes to the message box and comes back to the button.
 */
// `raised` lifts it above a sticky bar at the bottom of the page (the preferences form).
export function AdvisorChat({ wishId, raised = false }: { wishId: string; raised?: boolean }) {
  const { t } = useTranslation('chat')
  const [open, setOpen] = useState(false)
  const opener = useRef<HTMLButtonElement>(null)
  const titleId = useId()
  const dialogId = useId()

  const close = () => {
    setOpen(false)
    opener.current?.focus()
  }
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      event.stopPropagation()
      close()
    }
  }

  return (
    <div className={`pointer-events-none fixed inset-x-0 z-40 flex flex-col items-end gap-3 p-4 md:inset-x-auto md:end-0 ${raised ? 'bottom-18 md:bottom-22' : 'bottom-0'}`}>
      {open && (
        <section
          id={dialogId}
          role="dialog"
          aria-labelledby={titleId}
          onKeyDown={onKeyDown}
          className="pointer-events-auto flex max-h-[70vh] w-full flex-col rounded-2xl border border-line bg-white shadow-xl md:w-[380px]"
        >
          <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
            <div>
              <h2 id={titleId} className="m-0 text-lg">
                {t('title')}
              </h2>
              <p className="m-0 text-xs text-muted">{t('intro')}</p>
            </div>
            <button
              type="button"
              onClick={close}
              aria-label={t('close')}
              className="inline-flex size-11 shrink-0 items-center justify-center rounded-full text-ink"
            >
              <X aria-hidden="true" className="size-5" />
            </button>
          </header>
          <ChatThread wishId={wishId} side="client" autoFocus />
        </section>
      )}
      <Button
        ref={opener}
        type="button"
        variant="coral"
        aria-expanded={open}
        aria-controls={open ? dialogId : undefined}
        onClick={() => (open ? close() : setOpen(true))}
        className="pointer-events-auto shadow-lg"
      >
        <MessageCircle aria-hidden="true" className="size-5" />
        <span className={open ? 'sr-only md:not-sr-only' : undefined}>{t('open')}</span>
      </Button>
    </div>
  )
}

/**
 * The conversation of a wish and the box to write in, polled while shown. The client sees
 * "the agency" for staff lines; the agent sees "Client" for the client's.
 */
export function ChatThread({ wishId, side, autoFocus = false }: { wishId: string; side: Side; autoFocus?: boolean }) {
  const { t, i18n } = useTranslation('chat')
  const messages = useWishMessages(wishId, true)
  const post = usePostMessage(wishId)
  const [draft, setDraft] = useState('')
  const box = useRef<HTMLTextAreaElement>(null)
  const log = useRef<HTMLOListElement>(null)
  const inputId = useId()
  const errorId = useId()
  const count = messages.data?.length ?? 0

  useEffect(() => {
    if (autoFocus) box.current?.focus()
  }, [autoFocus])
  // Scroll the log itself, never the page: scrollIntoView would pull the agent's page down
  // to the chat on every poll.
  useEffect(() => {
    const list = log.current
    if (list) list.scrollTop = list.scrollHeight
  }, [count])

  const send = (event?: FormEvent) => {
    event?.preventDefault()
    const body = draft.trim()
    if (!body || post.isPending) return
    post.mutate(body, { onSuccess: () => setDraft('') })
    // The button is disabled while sending: keep focus in the box, so Escape still closes.
    box.current?.focus()
  }
  const author = (message: ChatMessage) =>
    message.mine ? t('you') : message.from_agency ? t('agency') : t('client')
  const time = (iso: string) => new Date(iso).toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' })

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ol
        ref={log}
        role="log"
        aria-label={t('conversation')}
        aria-live="polite"
        className="m-0 grid min-h-24 flex-1 list-none content-start gap-3 overflow-y-auto p-4"
      >
        {messages.isError && !messages.data && <li className="text-sm text-danger">{t('loadFailed')}</li>}
        {messages.data?.length === 0 && <li className="text-sm text-muted">{t('empty')}</li>}
        {messages.data?.map((message) => {
          const fromMe = side === 'client' ? !message.from_agency : message.from_agency
          return (
            <li key={message.id} className={fromMe ? 'grid justify-items-end' : 'grid justify-items-start'}>
              <span className="text-xs text-muted">
                <span>{author(message)}</span> · <time dateTime={message.sent_at}>{time(message.sent_at)}</time>
              </span>
              <p
                className={`m-0 max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${fromMe ? 'bg-ink text-white' : 'bg-ivory text-ink'}`}
              >
                {message.body}
              </p>
            </li>
          )
        })}
      </ol>
      <form onSubmit={send} className="grid gap-2 border-t border-line p-3">
        <label htmlFor={inputId} className="sr-only">
          {t('label')}
        </label>
        <textarea
          ref={box}
          id={inputId}
          value={draft}
          maxLength={MAX_LENGTH}
          rows={2}
          placeholder={t('placeholder')}
          aria-describedby={post.isError ? errorId : undefined}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            // Enter sends, Shift+Enter goes to a new line. Not while an IME composes a word.
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) send(event)
          }}
          className="w-full resize-none rounded-xl border border-line px-3 py-2 text-sm"
        />
        {post.isError && (
          <p id={errorId} role="alert" className="m-0 text-sm text-danger">
            {t('sendFailed')}
          </p>
        )}
        <Button type="submit" size="md" disabled={!draft.trim() || post.isPending} className="justify-self-end">
          {post.isPending ? t('sending') : t('send')}
        </Button>
      </form>
    </div>
  )
}
