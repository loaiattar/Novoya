import { type ReactNode, useId } from 'react'

import { cn } from '@/lib/utils'

type Props = {
  label: ReactNode
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  /** A short help line under the label. */
  hint?: string
  className?: string
}

/** A checkbox with its label. The whole row (44px high) is the tap target. */
export function CheckField({ label, checked, onChange, disabled, hint, className }: Props) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  return (
    <div className={cn('my-2', className)}>
      <label
        htmlFor={id}
        className={cn('flex min-h-11 items-center gap-3 text-sm', disabled ? 'text-muted' : 'cursor-pointer')}
      >
        <input
          id={id}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
          aria-describedby={hintId}
          className="size-6 shrink-0 accent-ink disabled:opacity-60"
        />
        <span>{label}</span>
      </label>
      {hint && (
        <small id={hintId} className="block ps-9 text-xs text-muted">
          {hint}
        </small>
      )}
    </div>
  )
}
