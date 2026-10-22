import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import { useAgency } from '../../hooks/ui/useAgency'
import { Eyebrow } from '../atoms/Eyebrow'
import { HomeLink } from '../molecules/HomeLink'
import { LanguageChoice } from './LanguageChoice'

const YEAR = new Date().getFullYear()

/** The footer of every page but sign-in. Only confirmed agency facts appear. */
export function SiteFooter({ className }: { className?: string }) {
  const { t } = useTranslation()
  const agency = useAgency()
  return (
    <footer className={cn('bg-ink text-ivory px-5 pt-12 pb-4 md:px-[5vw] md:pt-14', className)}>
      <div className="grid gap-10 md:grid-cols-[1fr_auto] md:items-start">
        <div className="grid gap-3">
          <HomeLink light />
          {agency.tagline && <p className="m-0 max-w-[22rem] font-serif text-base">{agency.tagline}</p>}
          {agency.foundedYear && (
            <p className="m-0 text-xs text-ivory/70">{t('footer.since', { year: agency.foundedYear })}</p>
          )}
        </div>
        <address className="m-0 grid content-start text-sm not-italic text-ivory">
          <Eyebrow light className="mb-1">{t('footer.contact')}</Eyebrow>
          {agency.address && <p className="m-0">{agency.address}</p>}
          {agency.phone && (
            <a href={agency.phone.href} className="min-h-11 w-fit content-center text-ivory underline-offset-4 hover:underline">
              {agency.phone.display}
            </a>
          )}
          {agency.email && (
            <a
              href={`mailto:${agency.email}`}
              className="min-h-11 w-fit content-center break-all text-ivory underline-offset-4 hover:underline"
            >
              {agency.email}
            </a>
          )}
          {agency.social.length > 0 && (
            <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-2 p-0">
              {agency.social.map((link) => (
                <li key={link.network}>
                  <a
                    href={link.href}
                    rel="noreferrer"
                    className="min-h-11 content-center capitalize text-ivory underline-offset-4 hover:underline"
                  >
                    {link.network}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </address>
      </div>
      {/* One line on a wide screen: the links, then the language and the copyright at the end. */}
      <div className="mt-10 flex flex-wrap items-center gap-x-8 border-t border-ivory/20 pt-3 text-sm md:mt-12">
        <nav aria-label={t('footer.nav')} className="flex flex-wrap items-center gap-x-6">
          <Link to="/destinations" className="min-h-11 content-center text-ivory underline-offset-4 hover:underline">
            {t('footer.destinations')}
          </Link>
          <Link to="/legal" className="min-h-11 content-center text-ivory underline-offset-4 hover:underline">
            {t('footer.legalNotices')}
          </Link>
          <Link to="/privacy" className="min-h-11 content-center text-ivory underline-offset-4 hover:underline">
            {t('footer.privacy')}
          </Link>
        </nav>
        <div className="flex flex-wrap items-center gap-x-6 md:ms-auto">
          {/* Pulled back by the buttons' own padding: "EN" starts on the line's edge on a phone. */}
          <LanguageChoice light className="-ms-3 md:ms-0" />
          <span className="text-xs text-ivory/70">{t('footer.copyright', { year: YEAR, name: agency.displayName })}</span>
        </div>
      </div>
    </footer>
  )
}
