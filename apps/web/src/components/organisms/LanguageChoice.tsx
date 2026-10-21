import { useTranslation } from 'react-i18next'

import { useLanguageChoice } from '../../hooks/i18n/useLanguageChoice'
import { LanguageSwitch } from '../molecules/LanguageSwitch'

/** The EN / FR switch, wired: saved on the account when signed in, on this browser always. */
export function LanguageChoice({ className, light }: { className?: string; light?: boolean }) {
  const { t } = useTranslation()
  const { language, choose, saving, failed } = useLanguageChoice()
  return (
    <LanguageSwitch
      value={language}
      onChange={choose}
      busy={saving}
      error={failed ? t('language.failed') : undefined}
      className={className}
      light={light}
    />
  )
}
