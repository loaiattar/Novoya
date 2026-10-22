import { useId, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

type Props = {
  label: string
  /** The saved price, a decimal string from the API, or null when there is none yet. */
  value: string | null
  /** Saves the typed amount (a decimal string with a dot). Rejects when it was not saved. */
  onSave: (amount: string) => Promise<unknown>
  /** What to say by the field when onSave rejected, from its error. */
  errorText: (error: unknown) => string
  /** The price waits for the agent's confirmation: saving it, even unchanged, confirms it. */
  unconfirmed?: boolean
  disabled?: boolean
}

const shown = (value: string | null) => (value === null ? '' : value.replace(/\.00$/, ''))

/**
 * A price in euros, saved when the field loses focus or on Enter. What was typed stays when
 * the save fails, with the reason by the field, so the agent can fix it instead of typing again.
 */
export function PriceField({ label, value, onSave, errorText, unconfirmed = false, disabled = false }: Props) {
  const [draft, setDraft] = useState(shown(value))
  const [error, setError] = useState<string | null>(null)
  const errorId = useId()
  // The amount on its way to the API: Enter then blur must not send it twice.
  const sending = useRef<string | null>(null)

  // A newer price from the API (this save, another tab, a reload) replaces what was typed.
  // A failed save leaves the price as it was, so what was typed stays.
  const [saved, setSaved] = useState(value)
  if (value !== saved) {
    setSaved(value)
    setDraft(shown(value))
    setError(null)
  }

  const save = () => {
    const amount = draft.trim().replace(',', '.')
    // The API cannot clear a price: an emptied field shows the saved one again.
    if (amount === '') {
      setDraft(shown(value))
      setError(null)
      return
    }
    const unchanged = value !== null && Number(amount) === Number(value)
    if (unchanged) setError(null)
    if ((unchanged && !unconfirmed) || amount === sending.current) return
    setError(null)
    sending.current = amount
    onSave(amount)
      .catch((reason: unknown) => setError(errorText(reason)))
      .finally(() => {
        sending.current = null
      })
  }

  return (
    <span className="grid gap-1">
      <span className="flex items-center gap-2">
        <input
          type="text"
          inputMode="decimal"
          aria-label={label}
          aria-invalid={error !== null}
          aria-describedby={error ? errorId : undefined}
          value={draft}
          disabled={disabled}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={save}
          onKeyDown={(event) => event.key === 'Enter' && save()}
          className={cn(
            'min-h-11 w-28 rounded-[3px] border bg-white px-3 text-end font-serif',
            error ? 'border-danger' : 'border-line',
          )}
        />
        <span aria-hidden="true" className="text-muted">
          €
        </span>
      </span>
      {error && (
        <small id={errorId} role="alert" className="text-xs text-danger">
          {error}
        </small>
      )}
    </span>
  )
}
