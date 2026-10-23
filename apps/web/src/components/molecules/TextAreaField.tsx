import { Textarea } from '../atoms/Input'
import { Field } from './Field'

type Props = {
  label: string
  value: string
  onChange: (value: string) => void
  onBlur?: () => void
  rows?: number
  maxLength?: number
  readOnly?: boolean
  hint?: string
  error?: string
  className?: string
}

/** A labelled text on several lines, with its error. */
export function TextAreaField({
  label,
  value,
  onChange,
  onBlur,
  rows = 3,
  maxLength,
  readOnly,
  hint,
  error,
  className,
}: Props) {
  return (
    <Field label={label} hint={hint} error={error} className={className}>
      {({ id, describedBy, invalid }) => (
        <Textarea
          id={id}
          value={value}
          rows={rows}
          maxLength={maxLength}
          readOnly={readOnly}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onBlur}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
        />
      )}
    </Field>
  )
}
