import { createFileRoute, Link } from '@tanstack/react-router'
import { type ReactNode, useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { HomeLink } from '../components/molecules/HomeLink'
import { SiteFooter } from '../components/organisms/SiteFooter'
import { useAgency } from '../hooks/ui/useAgency'

export const Route = createFileRoute('/privacy')({
  component: PrivacyPage,
})

// Public: linked from the sign-in page and from Google's consent screen.
// In reading order. A list has items, a paragraph a body; "rights" closes the page with a link.
type ListKey = 'data' | 'processors' | 'retention'
type ParagraphKey = 'controller' | 'never' | 'reviews' | 'cookies' | 'basis'
const SECTIONS: ({ list: ListKey } | { paragraph: ParagraphKey })[] = [
  { paragraph: 'controller' },
  { list: 'data' },
  { paragraph: 'never' },
  { list: 'processors' },
  { list: 'retention' },
  { paragraph: 'reviews' },
  { paragraph: 'cookies' },
  { paragraph: 'basis' },
]

function PrivacyPage() {
  const { t } = useTranslation('privacy')
  const agency = useAgency()
  const values = { name: agency.displayName, email: agency.email ?? agency.displayName }

  useEffect(() => {
    const previous = document.title
    document.title = `${t('title')} — ${agency.tradeName}`
    return () => {
      document.title = previous
    }
  }, [agency.tradeName, t])

  const section = (key: ListKey | ParagraphKey | 'rights', body: ReactNode) => (
    <section key={key} aria-labelledby={`privacy-${key}`} className="mt-10">
      <h2 id={`privacy-${key}`} className="mb-3 font-serif text-2xl">
        {t(`${key}.title`)}
      </h2>
      {body}
    </section>
  )
  const paragraph = (key: ParagraphKey) => section(key, <p className="m-0">{t(`${key}.body`, values)}</p>)
  const list = (key: ListKey) =>
    section(
      key,
      <ul className="m-0 grid list-disc gap-2 ps-5">
        {t(`${key}.items`, { ...values, returnObjects: true }).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>,
    )

  // Who is responsible, with the agency's confirmed address and phone (brand/agency.json).
  const controller = () =>
    section(
      'controller',
      <>
        <p className="m-0">{t('controller.body', values)}</p>
        {(agency.address || agency.phone) && (
          <address className="mt-3 grid not-italic">
            {agency.address && <span>{agency.address}</span>}
            {agency.phone && (
              <a href={agency.phone.href} className="inline-flex min-h-11 w-fit items-center underline underline-offset-4">
                {agency.phone.display}
              </a>
            )}
          </address>
        )}
      </>,
    )

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <header className="flex h-18 items-center border-b border-line px-5 md:h-22 md:px-[5vw]">
        <HomeLink />
      </header>
      <main className="mx-auto w-full max-w-[640px] flex-1 px-5 py-10 text-sm leading-relaxed md:px-8 md:py-16">
        <h1 className="mb-3 font-serif text-[40px] leading-none md:text-[56px]">{t('title')}</h1>
        <p className="mb-6 text-muted">{t('updated')}</p>
        <p className="m-0">{t('intro', values)}</p>
        {SECTIONS.map((entry) =>
          'list' in entry ? list(entry.list) : entry.paragraph === 'controller' ? controller() : paragraph(entry.paragraph),
        )}
        {section(
          'rights',
          <>
            <p className="m-0">{t('rights.body', values)}</p>
            <Link to="/settings" className="mt-3 inline-flex min-h-11 items-center underline underline-offset-4">
              {t('rights.settings')}
            </Link>
          </>,
        )}
      </main>
      <SiteFooter />
    </div>
  )
}
