import { type ReactNode, useId } from 'react'

import { cn } from '@/lib/utils'

type Props = {
  label: ReactNode
  /** A short help line under the field. */
  hint?: ReactNode
  error?: string
  className?: string
  /** The control. It receives the id, and the ids of the hint and the error. */
  children: (ids: { id: string; describedBy?: string; invalid: boolean }) => ReactNode
}

/** A label, a control and its help or error, linked for screen readers. */
export function Field({ label, hint, error, className, children }: Props) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className={cn('my-4', className)}>
      <label htmlFor={id} className="mb-2 block text-sm">
        {label}
      </label>
      {children({ id, describedBy, invalid: Boolean(error) })}
      {hint && (
        <p id={hintId} className="mt-1.5 text-xs text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="mt-1.5 text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  )
}
