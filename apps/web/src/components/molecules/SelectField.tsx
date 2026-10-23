import { Field } from './Field'

type Props<T extends string> = {
  label: string
  value: T | ''
  options: { value: T | ''; label: string }[]
  onChange: (value: T | '') => void
  disabled?: boolean
  hint?: string
  error?: string
  className?: string
}

/** A labelled list to pick one value from, with its error. */
export function SelectField<T extends string>({
  label,
  value,
  options,
  onChange,
  disabled,
  hint,
  error,
  className,
}: Props<T>) {
  return (
    <Field label={label} hint={hint} error={error} className={className}>
      {({ id, describedBy, invalid }) => (
        <select
          id={id}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value as T | '')}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className="block min-h-[52px] w-full border border-line bg-white px-3 text-base text-ink aria-invalid:border-danger disabled:bg-ivory disabled:text-muted"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  )
}
