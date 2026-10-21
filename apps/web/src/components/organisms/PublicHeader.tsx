import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { Button } from '../atoms/Button'
import { HomeLink } from '../molecules/HomeLink'
import { LanguageChoice } from './LanguageChoice'

/** The header over the landing page's photo, for visitors. */
export function PublicHeader({ signedIn = false }: { signedIn?: boolean }) {
  const { t } = useTranslation('header')
  return (
    <header className="absolute inset-x-0 top-0 z-10 flex h-18 items-center justify-between px-5 md:h-22 md:px-[5vw]">
      <HomeLink light />
      <nav aria-label={t('mainNav')} className="flex items-center gap-4 text-sm text-white md:gap-7">
        <a href="#voyages" className="hidden min-h-11 items-center text-white no-underline md:inline-flex">
          {t('inspirations')}
        </a>
        <a href="#methode" className="hidden min-h-11 items-center text-white no-underline md:inline-flex">
          {t('ourMethod')}
        </a>
        <LanguageChoice light />
        <Button asChild variant="glass">
          {signedIn ? <Link to="/wish">{t('mySpace')}</Link> : <Link to="/login">{t('signIn')}</Link>}
        </Button>
      </nav>
    </header>
  )
}
