import { cn } from '@/lib/utils'

type Props = {
  label: string
  selected: boolean
  onToggle: () => void
  className?: string
}

/** A tag the user can pick or unpick. Screen readers hear it as a pressed button. */
export function TagToggle({ label, selected, onToggle, className }: Props) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onToggle}
      className={cn(
        'min-h-11 rounded-full border border-line px-4 py-2.5 text-sm transition-colors',
        selected ? 'border-ink bg-ink text-white' : 'bg-transparent hover:border-ink',
        className,
      )}
    >
      {selected && (
        <span aria-hidden="true" className="mr-1.5 text-coral">
          ✓
        </span>
      )}
      {label}
    </button>
  )
}
