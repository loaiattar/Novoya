import { type FormEvent, type KeyboardEvent, type Ref, useId } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import { isApplePlatform } from '@/lib/platform'

import { WishProgress } from './WishProgress'

type Props = {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  pending?: boolean
  /** Why the wish was not sent. */
  error?: string
  /** Sends the text in the box again (the client may have changed it); shown next to the error. */
  onRetry?: () => void
  textareaRef?: Ref<HTMLTextAreaElement>
}

// The model can take up to 20 s: three steps of 3 s, then the last one waits.
const PROGRESS_STEPS = ['read', 'destinations', 'preferences'] as const
const PROGRESS_EVERY_MS = 3000

const kbd = 'rounded-[3px] border border-line px-1.5 py-0.5 font-sans'

/** The big white box where the client writes their wish. ⌘/Ctrl + Enter sends it. */
export function WishComposer({ value, onChange, onSubmit, pending = false, error, onRetry, textareaRef }: Props) {
  const id = useId()
  const errorId = `${id}-error`
  const { t } = useTranslation('wish')
  const { t: tCommon } = useTranslation('common')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!pending) onSubmit()
  }
  const sendOnShortcut = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      if (!pending) onSubmit()
    }
  }

  return (
    <form
      onSubmit={submit}
      aria-busy={pending}
      className="w-full rounded-[3px] border border-ink/10 bg-white p-[19px] text-left shadow-card md:w-[min(760px,90vw)] md:p-[25px]"
    >
      <label htmlFor={id} className="sr-only">
        {t('composerLabel')}
      </label>
      <textarea
        id={id}
        ref={textareaRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={sendOnShortcut}
        disabled={pending}
        aria-invalid={Boolean(error) && !pending}
        aria-describedby={error && !pending ? errorId : undefined}
        placeholder={t('placeholder')}
        className="h-[90px] w-full resize-none border-0 bg-transparent font-serif text-xl text-ink placeholder:text-muted disabled:text-ink/60"
      />
      {error && !pending && (
        <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
          <p id={errorId} role="alert" className="text-sm text-danger">
            {error}
          </p>
          {onRetry && (
            <button type="button" onClick={onRetry} className="min-h-11 text-sm font-medium text-ink underline">
              {tCommon('tryAgain')}
            </button>
          )}
        </div>
      )}
      <div className="flex items-center justify-between gap-3">
        {/* Always mounted, so the first step is written into a status region screen readers know. */}
        <WishProgress
          active={pending}
          steps={PROGRESS_STEPS.map((step) => t(`progress.${step}`))}
          everyMs={PROGRESS_EVERY_MS}
        />
        {!pending && (
          <span className="text-xs text-muted">
            <Trans
              t={t}
              i18nKey="shortcut"
              values={{ key: isApplePlatform() ? '⌘' : 'Ctrl' }}
              components={[<kbd key="cmd" className={kbd} />, <kbd key="enter" className={kbd} />]}
            />
          </span>
        )}
        <button
          type="submit"
          aria-label={pending ? t('sending') : t('send')}
          disabled={pending}
          className="grid size-11 shrink-0 place-items-center rounded-full bg-coral text-xl text-ink transition hover:bg-coral-light disabled:opacity-60"
        >
          {/* While sending, the loader beside it turns: one spinner is enough. */}
          <span aria-hidden="true">↑</span>
        </button>
      </div>
    </form>
  )
}
