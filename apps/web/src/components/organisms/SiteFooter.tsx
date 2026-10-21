import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useAgency } from '../../hooks/ui/useAgency'
import { HomeLink } from '../molecules/HomeLink'
import { LanguageChoice } from './LanguageChoice'

const YEAR = new Date().getFullYear()

/** The footer of the public pages. Only confirmed agency facts appear. */
export function SiteFooter() {
  const { t } = useTranslation()
  const agency = useAgency()
  return (
    <footer className="grid gap-8 bg-paper px-5 py-12 md:grid-cols-[auto_1fr_auto] md:items-start md:gap-10 md:px-[5vw] md:pt-16 md:pb-9">
      <div className="grid gap-3">
        <HomeLink />
        {agency.tagline && <p className="m-0 max-w-[22rem] font-serif text-base">{agency.tagline}</p>}
        {agency.foundedYear && (
          <p className="m-0 text-xs text-muted">{t('footer.since', { year: agency.foundedYear })}</p>
        )}
      </div>
      <address className="m-0 grid gap-2 text-sm not-italic text-ink">
        {agency.address && <p className="m-0">{agency.address}</p>}
        {agency.phone && (
          <a href={agency.phone.href} className="min-h-11 w-fit content-center text-ink underline-offset-4 hover:underline">
            {agency.phone.display}
          </a>
        )}
        {agency.email && (
          <a
            href={`mailto:${agency.email}`}
            className="min-h-11 w-fit content-center break-all text-ink underline-offset-4 hover:underline"
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
                  className="min-h-11 content-center capitalize text-ink underline-offset-4 hover:underline"
                >
                  {link.network}
                </a>
              </li>
            ))}
          </ul>
        )}
      </address>
      <div className="grid gap-3 text-sm">
        <Link to="/destinations" className="min-h-11 w-fit content-center text-ink underline-offset-4 hover:underline">
          {t('footer.destinations')}
        </Link>
        <Link to="/legal" className="min-h-11 w-fit content-center text-ink underline-offset-4 hover:underline">
          {t('footer.legalNotices')}
        </Link>
        <LanguageChoice />
        <span className="text-xs text-muted">{t('footer.copyright', { year: YEAR, name: agency.displayName })}</span>
      </div>
    </footer>
  )
}
