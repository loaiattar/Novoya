import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Input } from '../atoms/Input'
import { Field } from './Field'

type Props = {
  label: string
  type?: 'text' | 'email' | 'password' | 'tel' | 'date'
  name?: string
  value: string
  onChange: (value: string) => void
  onBlur?: () => void
  autoComplete?: string
  placeholder?: string
  required?: boolean
  maxLength?: number
  /** Shown, but cannot be changed (a field owned elsewhere). */
  readOnly?: boolean
  inputMode?: 'numeric' | 'text' | 'email' | 'tel'
  hint?: string
  error?: string
  className?: string
}

/** A labelled form field (e-mail, password, text, date), with its error. A password can be shown. */
export function TextField({
  label,
  type = 'text',
  name,
  value,
  onChange,
  onBlur,
  autoComplete,
  placeholder,
  required,
  maxLength,
  readOnly,
  inputMode,
  hint,
  error,
  className,
}: Props) {
  const [shown, setShown] = useState(false)
  const { t } = useTranslation('auth')
  const isPassword = type === 'password'

  return (
    <Field label={label} hint={hint} error={error} className={className}>
      {({ id, describedBy, invalid }) => (
        <div className="relative">
          <Input
            id={id}
            name={name}
            type={isPassword && shown ? 'text' : type}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onBlur={onBlur}
            autoComplete={autoComplete}
            placeholder={placeholder}
            required={required}
            maxLength={maxLength}
            readOnly={readOnly}
            inputMode={inputMode}
            aria-invalid={invalid || undefined}
            aria-describedby={describedBy}
            className={isPassword ? 'pe-24' : undefined}
          />
          {isPassword && (
            <button
              type="button"
              aria-pressed={shown}
              onClick={() => setShown(!shown)}
              className="absolute top-1/2 end-1 min-h-11 -translate-y-1/2 px-3 text-xs underline underline-offset-4"
            >
              {shown ? t('hidePassword') : t('showPassword')}
            </button>
          )}
        </div>
      )}
    </Field>
  )
}
