import { useTranslation } from 'react-i18next'

import type { Locale } from '../../domain/i18n/locale'
import { cn } from '@/lib/utils'

// Each language is named in itself, as everywhere: a French reader looks for "Français".
const LANGUAGES: { locale: Locale; short: string; name: string }[] = [
  { locale: 'en', short: 'EN', name: 'English' },
  { locale: 'fr', short: 'FR', name: 'Français' },
]

type Props = {
  value: Locale
  onChange: (locale: Locale) => void
  /** The choice is being saved: the buttons wait. */
  busy?: boolean
  /** Shown when the choice could not be saved. */
  error?: string
  className?: string
  /** White text, over a photo. */
  light?: boolean
}

/** EN / FR, the current one pressed. Screen readers hear a "Language" group of two buttons. */
export function LanguageSwitch({ value, onChange, busy = false, error, className, light = false }: Props) {
  const { t } = useTranslation()
  return (
    <div className={cn('flex flex-wrap items-center gap-x-3 gap-y-1', className)}>
      <div role="group" aria-label={t('language.label')} aria-busy={busy} className="flex items-center">
        {LANGUAGES.map(({ locale, short, name }) => (
          <button
            key={locale}
            type="button"
            lang={locale}
            // Voice control users say what they see: the name starts with it.
            aria-label={`${short}, ${name}`}
            aria-pressed={value === locale}
            disabled={busy}
            onClick={() => onChange(locale)}
            className={cn(
              'min-h-11 min-w-11 px-2 text-xs font-semibold tracking-[0.15em] underline-offset-4 disabled:opacity-60',
              light
                ? value === locale
                  ? 'text-white underline'
                  : 'text-white/75 hover:text-white'
                : value === locale
                  ? 'text-ink underline'
                  : 'text-muted hover:text-ink',
            )}
          >
            {short}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className={cn('m-0 text-xs', light ? 'text-white' : 'text-danger')}>
          {error}
        </p>
      )}
    </div>
  )
}
