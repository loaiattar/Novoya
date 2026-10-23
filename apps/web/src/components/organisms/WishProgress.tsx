import { useEffect, useState } from 'react'

type Props = {
  /** What is being done, in order. The last one stays until the parent stops the loader. */
  steps: readonly string[]
  /** How long each step shows before the next one. */
  everyMs: number
  /**
   * Whether the work runs. While it does not, only an empty status region stays in the page, so
   * screen readers already know it when the first step is written into it.
   */
  active?: boolean
  /** Read with the steps, under them. */
  note?: string
  /** `dark` for the ink background of the plan screen. */
  tone?: 'light' | 'dark'
  className?: string
}

/**
 * Timed steps shown while the model works (#166). The API does not report its progress: the
 * steps only tell the client the page is not stuck. The parent stops it as soon as the answer
 * arrives, whatever step it is on.
 */
export function WishProgress({ steps, everyMs, active = true, note, tone = 'light', className = '' }: Props) {
  // `null` until the first step is written: the region is mounted empty first, then filled.
  const [current, setCurrent] = useState<number | null>(null)
  const count = steps.length

  // One timer per step, all set at the start: nothing runs after the last step. The first one
  // fires on the next tick, so the empty region is in the page before its first text.
  useEffect(() => {
    if (!active) return
    const timers = Array.from({ length: count }, (_, index) => setTimeout(() => setCurrent(index), index * everyMs))
    return () => {
      timers.forEach(clearTimeout)
      setCurrent(null)
    }
  }, [active, count, everyMs])

  const shown = active && current !== null
  const dark = tone === 'dark'
  return (
    <div className={shown ? `flex items-start gap-3 text-left ${className}` : 'contents'}>
      {shown && (
        <span
          aria-hidden="true"
          className={`mt-0.5 size-4 shrink-0 rounded-full border-2 border-t-transparent motion-safe:animate-spin ${
            dark ? 'border-coral' : 'border-ink'
          }`}
        />
      )}
      <div role="status" aria-atomic="false" className={shown ? `min-w-0 text-sm ${dark ? 'text-white' : 'text-ink'}` : 'sr-only'}>
        {shown && (
          <>
            <p>{steps[current]}…</p>
            <ol aria-hidden="true" className="mt-1.5 flex gap-1.5">
              {steps.map((step, index) => (
                <li
                  key={step}
                  className={`h-1 w-6 rounded-full ${
                    index <= current ? 'bg-coral' : dark ? 'bg-white/20' : 'bg-ink/15'
                  }`}
                />
              ))}
            </ol>
            {note && <p className={`mt-3 ${dark ? 'text-white/80' : 'text-muted'}`}>{note}</p>}
          </>
        )}
      </div>
    </div>
  )
}
