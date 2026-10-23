import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, useNavigate, useRouter } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError, isUnauthenticated } from '../../../api/errors'
import { getMeQueryKey, sendWishMutation } from '../../../api/generated/@tanstack/react-query.gen'
import { type CachedWish, type WishResponse, wishQueryKey } from '../../../api/wishes'
import { Eyebrow } from '../../../components/atoms/Eyebrow'
import { Seal } from '../../../components/atoms/Seal'
import { CoverageSuggestions } from '../../../components/organisms/CoverageSuggestions'
import { WishComposer } from '../../../components/organisms/WishComposer'
import { AppShell } from '../../../components/templates/AppShell'
import { givenName } from '../../../domain/auth/session'
import { destinationLabel, destinationPhoto, destinationPlace } from '../../../domain/wish/destination'
import { sendWishError, WISH_MAX_LENGTH, wishTextError, type WishTextErrorKey } from '../../../domain/wish/wish'

export const Route = createFileRoute('/_authenticated/wish/')({
  component: WishPage,
})

// Ready-made wishes to start from; texts in wish.json, sparks.<id>.
const SPARKS = ['cultureCalm', 'oceanMove'] as const

function WishPage() {
  const { me } = Route.useRouteContext()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const router = useRouter()
  const { t } = useTranslation('wish')
  const { t: tErrors } = useTranslation('errors')
  const textarea = useRef<HTMLTextAreaElement>(null)
  const [text, setText] = useState('')
  const [checkError, setCheckError] = useState<WishTextErrorKey>()
  // The last answer that keeps the client on this page: not covered, or no place named.
  const [answer, setAnswer] = useState<WishResponse>()

  // Set at once on send, not at the next render: a second ⌘/Ctrl + Enter in between sends nothing.
  const sending = useRef(false)
  // These callbacks still run once the client has left the page (a header link mid-send):
  // they must not pull them back to the panel, or to /login. The page can also still be
  // mounted while the next one loads: the location being left counts as gone too.
  const mounted = useRef(false)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])
  const stillHere = () => mounted.current && router.latestLocation.pathname.replace(/\/$/, '') === '/wish'
  const send = useMutation({
    ...sendWishMutation(),
    // Here and not in mutate(): this one still runs after send.reset().
    onSettled: () => {
      sending.current = false
    },
    // The session ended: the cached /me goes in every case, or the sign-in page (or the next
    // guarded page, if the client left) would still see a session. Sign in again and come back
    // here only from this page.
    onError: async (error) => {
      if (!isUnauthenticated(error)) return
      // Not while /me is being read (the next page's guard): removing it would cancel that
      // fetch, and the guard would show the error page. That fetch gets the 401 itself.
      if (queryClient.isFetching({ queryKey: getMeQueryKey() }) === 0) {
        queryClient.removeQueries({ queryKey: getMeQueryKey() })
      }
      if (!stillHere()) return
      await navigate({ to: '/login', search: { redirect: '/wish' }, replace: true })
    },
    onSuccess: async (wish) => {
      if (wish.status === 'panel_shown') {
        queryClient.setQueryData<CachedWish>(wishQueryKey(wish.id), { ...wish, text: text.trim() })
        if (!stillHere()) return
        await navigate({ to: '/wish/$wishId/preferences', params: { wishId: wish.id } })
        return
      }
      if (stillHere()) setAnswer(wish)
    },
  })

  const submit = () => {
    if (sending.current) return
    const error = wishTextError(text)
    setCheckError(error ?? undefined)
    if (error) return
    sending.current = true
    // The last answer goes: its "where?" status must not stay next to the progress.
    setAnswer(undefined)
    send.mutate({ body: { text: text.trim() } })
  }

  // The box was disabled while sending, which drops the keyboard focus: give it back when the
  // client stays here (an error, or a question). After a navigation the box is gone: no-op.
  const wasPending = useRef(false)
  useEffect(() => {
    // Only when the focus was lost, not when the client moved it elsewhere meanwhile. Lost is
    // on the body, or still in the composer: a browser may keep it on the disabled send button.
    const active = document.activeElement
    const lost = active === null || active === document.body || Boolean(textarea.current?.form?.contains(active))
    if (wasPending.current && !send.isPending && lost) textarea.current?.focus()
    wasPending.current = send.isPending
  }, [send.isPending])

  const startOver = (nextText: string) => {
    setAnswer(undefined)
    send.reset()
    sending.current = false
    setText(nextText)
    // After the view switches back, put the cursor at the end of the text.
    requestAnimationFrame(() => {
      textarea.current?.focus()
      textarea.current?.setSelectionRange(nextText.length, nextText.length)
    })
  }

  if (answer?.status === 'not_covered') {
    return (
      <AppShell>
        <main>
          <CoverageSuggestions
            place={answer.destination ? destinationPlace(answer.destination) : t('coverage.unknownPlace')}
            suggestions={answer.suggestions.map((destination) => ({
              key: destinationLabel(destination),
              label: destinationLabel(destination),
              image: destinationPhoto(destination),
              onPick: () => startOver(t('suggestionWish', { place: destinationPlace(destination) })),
            }))}
            onRephrase={() => startOver(text)}
          />
        </main>
      </AppShell>
    )
  }

  const refused = send.isError
    ? sendWishError(
        send.error instanceof ApiError ? send.error.code : undefined,
        send.error instanceof ApiError ? send.error.retryAfterSeconds : undefined,
      )
    : undefined
  // Only a network failure or a server error may go away by sending again.
  const retryable = send.isError && (!(send.error instanceof ApiError) || send.error.status >= 500)
  const sendError = refused ? tErrors(refused.key, { count: refused.count }) : undefined
  const textError = checkError ? tErrors(checkError, { max: WISH_MAX_LENGTH }) : undefined
  const firstName = givenName(me)

  return (
    <AppShell tone="ivory">
      <main className="flex min-h-[calc(100vh-72px)] flex-col items-center justify-center px-[18px] py-10 text-center md:min-h-[calc(100vh-88px)] md:px-5 md:py-[70px]">
        <Seal className="mb-5 size-[57px] shadow-[0_0_0_10px_rgb(242_183_5/0.1)]" />
        <Eyebrow>{firstName ? t('greeting', { name: firstName }) : t('greetingNoName')}</Eyebrow>
        <h1 className="mb-[23px] text-display-m">
          {t('titleStart')}
          <br />
          <em>{t('titleEnd')}</em>
        </h1>
        <p className="mb-8 text-muted">{t('subtitle')}</p>
        {answer?.status === 'draft' && (
          <p role="status" className="mb-4 max-w-[760px] text-ink">
            {t('askPlace')}
          </p>
        )}
        <WishComposer
          value={text}
          onChange={(value) => {
            setText(value)
            if (checkError) setCheckError(undefined)
          }}
          onSubmit={submit}
          pending={send.isPending}
          error={textError ?? sendError}
          onRetry={!textError && retryable ? submit : undefined}
          textareaRef={textarea}
        />
        <div className="mt-[22px] flex w-full items-center justify-start gap-2.5 overflow-x-auto md:w-auto md:justify-center">
          <span className="hidden text-xs text-muted md:inline">
            {answer?.status === 'draft' && answer.suggestions.length > 0
              ? t('ourDestinations')
              : t('sparksLabel')}
          </span>
          {(answer?.status === 'draft' && answer.suggestions.length > 0
            ? answer.suggestions.map(
                (destination) =>
                  [destinationLabel(destination), t('suggestionWish', { place: destinationPlace(destination) })] as const,
              )
            : SPARKS.map((spark) => [t(`sparks.${spark}.label`), t(`sparks.${spark}.wish`)] as const)
          ).map(([label, wish]) => (
            <button
              key={label}
              type="button"
              onClick={() => startOver(wish)}
              // A spark mid-send would leave the running request free to navigate later.
              disabled={send.isPending}
              className="min-h-11 shrink-0 rounded-full border border-line px-[13px] py-2 text-xs disabled:opacity-60"
            >
              {label}
            </button>
          ))}
        </div>
        <p className="mt-10 text-xs text-muted">{t('privacy')}</p>
      </main>
    </AppShell>
  )
}
