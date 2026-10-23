import { Link } from '@tanstack/react-router'
import { ArrowUp, ArrowUpRight } from 'lucide-react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import { useAgency } from '../../hooks/ui/useAgency'
import { Eyebrow } from '../atoms/Eyebrow'
import { HomeLink } from '../molecules/HomeLink'
import { LanguageChoice } from './LanguageChoice'

const YEAR = new Date().getFullYear()
// The agency is in Nantes: its local time, whatever the visitor's.
const AGENCY_TIME_ZONE = 'Europe/Paris'

const link = 'flex min-h-11 w-fit items-center text-ivory underline-offset-4 hover:underline'
const round =
  'grid size-11 shrink-0 place-items-center rounded-full border border-ivory/25 text-ivory transition-colors hover:border-coral hover:text-coral'

/** The footer of every page but sign-in. Only confirmed agency facts appear. */
export function SiteFooter({ className }: { className?: string }) {
  const { t } = useTranslation()
  const agency = useAgency()
  return (
    <footer className={cn('bg-ink text-ivory px-5 pt-12 pb-6 md:px-[5vw] md:pt-16', className)}>
      {/* Brand, two stacked lists of links, then the newsletter: one row on a wide screen. */}
      <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,2fr)_minmax(0,1.4fr)] lg:gap-8">
        <div className="grid content-start gap-3 sm:col-span-2 lg:col-span-1">
          <HomeLink light />
          {agency.tagline && <p className="m-0 max-w-[22rem] font-serif text-lg italic">{agency.tagline}</p>}
          <address className="m-0 grid text-sm not-italic text-ivory/70">
            {agency.address && <p className="m-0 flex min-h-11 items-center">{agency.address}</p>}
            {agency.phone && (
              <a href={agency.phone.href} className={cn(link, 'text-ivory/70')}>
                {agency.phone.display}
              </a>
            )}
            {agency.email && (
              <a href={`mailto:${agency.email}`} className={cn(link, 'break-all text-ivory/70')}>
                {agency.email}
              </a>
            )}
          </address>
        </div>
        <nav aria-label={t('footer.nav')} className="grid grid-cols-2 gap-x-8 sm:col-span-2 lg:col-span-1">
          <ul className="m-0 grid list-none content-start gap-1 p-0">
            <li>
              <Link to="/destinations" className={link}>
                {t('footer.destinations')}
              </Link>
            </li>
            <li>
              <Link to="/" hash="equipe" className={link}>
                {t('footer.about')}
              </Link>
            </li>
            <li>
              <Link to="/privacy" className={link}>
                {t('footer.privacy')}
              </Link>
            </li>
          </ul>
          <ul className="m-0 grid list-none content-start gap-1 p-0">
            <li>
              <Link to="/" hash="voyages" className={link}>
                {t('footer.weekends')}
              </Link>
            </li>
            {agency.email && (
              <li>
                <a href={`mailto:${agency.email}`} className={link}>
                  {t('footer.contact')}
                </a>
              </li>
            )}
            <li>
              <Link to="/legal" className={link}>
                {t('footer.legalNotices')}
              </Link>
            </li>
          </ul>
        </nav>
        <div className="flex flex-wrap items-start gap-4 sm:col-span-2 lg:col-span-1">
          <Newsletter />
          {agency.social.length > 0 && (
            <ul className="m-0 flex list-none gap-2 p-0">
              {agency.social.map((s) => (
                <li key={s.network}>
                  <a href={s.href} rel="noreferrer" aria-label={s.network} className={cn(round, 'capitalize')}>
                    {SOCIAL_ICONS[s.network] ?? s.network.slice(0, 2)}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <Trail />
      <div className="grid items-center gap-4 pt-6 font-mono text-xs tracking-[0.08em] text-ivory/60 sm:grid-cols-[1fr_auto_1fr]">
        <div className="grid gap-1">
          <span>{t('footer.copyright', { year: YEAR, name: agency.displayName })}</span>
          <LocalTime />
        </div>
        <BackToTop />
        {/* Pulled back by the buttons' own padding: "EN" starts on the line's edge on a phone. */}
        <LanguageChoice light className="-ms-3 font-sans sm:ms-0 sm:justify-self-end" />
      </div>
    </footer>
  )
}

/** A rule across, with a short dotted stretch ending on a coral dot: the road the agency takes aside. */
function Trail() {
  return (
    <div aria-hidden="true" className="relative mt-12 h-px bg-ivory/20">
      <span className="absolute -top-px start-1/2 w-[8rem] -translate-x-full border-t border-dashed border-ivory/40 rtl:translate-x-full" />
      <span className="absolute -top-[3px] start-1/2 size-[7px] -translate-x-1/2 rounded-full bg-coral rtl:translate-x-1/2" />
    </div>
  )
}

/** The field shows, but no newsletter is sent yet: a thank-you note says so. */
function Newsletter() {
  const { t } = useTranslation()
  const [sent, setSent] = useState(false)
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSent(true)
  }
  return (
    <form onSubmit={submit} className="grid min-w-0 flex-1 basis-64 gap-3">
      <label htmlFor="footer-newsletter">
        <Eyebrow light className="mb-0">
          {t('footer.newsletterLabel')}
        </Eyebrow>
      </label>
      <div className="flex items-center gap-2 border-b border-ivory/40 focus-within:border-coral">
        <input
          id="footer-newsletter"
          type="email"
          required
          autoComplete="email"
          placeholder={t('footer.newsletterPlaceholder')}
          className="min-h-11 min-w-0 flex-1 bg-transparent text-sm text-ivory placeholder:text-ivory/50 focus-visible:outline-none"
        />
        <button
          type="submit"
          aria-label={t('footer.newsletterSubmit')}
          className="mb-1.5 grid size-11 shrink-0 place-items-center rounded-full bg-coral text-ink transition-colors hover:bg-coral-light"
        >
          <ArrowUpRight aria-hidden="true" className="size-5" />
        </button>
      </div>
      {/* A live region, not role="status": the pages keep that one for their own news. */}
      <p aria-live="polite" className="m-0 min-h-4 text-xs text-ivory/70">
        {sent && t('footer.newsletterSoon')}
      </p>
    </form>
  )
}

/** The time in Nantes, to the minute. */
function LocalTime() {
  const { t, i18n } = useTranslation()
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30_000)
    return () => window.clearInterval(timer)
  }, [])
  const time = new Intl.DateTimeFormat(i18n.language, {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: AGENCY_TIME_ZONE,
  }).format(now)
  return <span className="uppercase">{t('footer.localTime', { time })}</span>
}

function BackToTop() {
  const { t } = useTranslation()
  function toTop() {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' })
  }
  return (
    <button type="button" onClick={toTop} aria-label={t('footer.backToTop')} className={cn(round, 'border-coral text-coral hover:bg-coral hover:text-ink sm:justify-self-center')}>
      <ArrowUp aria-hidden="true" className="size-5" />
    </button>
  )
}

// Brand marks are not in lucide: the two networks the agency may list, drawn here.
const SOCIAL_ICONS: Record<string, ReactNode> = {
  facebook: (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="currentColor">
      <path d="M13.5 21v-7.5h2.5l.4-3h-2.9V8.6c0-.9.3-1.5 1.5-1.5h1.5V4.4a20 20 0 0 0-2.2-.1c-2.2 0-3.7 1.3-3.7 3.8v2.4H8v3h2.6V21h2.9Z" />
    </svg>
  ),
  instagram: (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
    </svg>
  ),
}
