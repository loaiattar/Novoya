import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useAgency } from '../../hooks/ui/useAgency'
import { Logo } from '../atoms/Logo'

/** The agency mark, as a link home. */
export function HomeLink({ light = false }: { light?: boolean }) {
  const { t } = useTranslation()
  const agency = useAgency()
  return (
    <Link to="/" aria-label={t('homeLink', { name: agency.tradeName })} className="flex min-h-11 items-center no-underline">
      <Logo light={light} decorative />
    </Link>
  )
}
