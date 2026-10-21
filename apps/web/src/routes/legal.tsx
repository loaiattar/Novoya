import { createFileRoute } from '@tanstack/react-router'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { HomeLink } from '../components/molecules/HomeLink'
import { SiteFooter } from '../components/organisms/SiteFooter'
import { useAgency } from '../hooks/ui/useAgency'

export const Route = createFileRoute('/legal')({
  component: LegalPage,
})

function LegalPage() {
  const { t } = useTranslation('legal')
  const agency = useAgency()

  useEffect(() => {
    const previous = document.title
    document.title = `${t('title')} — ${agency.tradeName}`
    return () => {
      document.title = previous
    }
  }, [agency.tradeName, t])

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <header className="flex h-18 items-center border-b border-line px-5 md:h-22 md:px-[5vw]">
        <HomeLink />
      </header>
      <main className="mx-auto w-full max-w-[640px] flex-1 px-5 py-10 md:px-8 md:py-16">
        <h1 className="mb-8 font-serif text-[40px] leading-none md:text-[56px]">{t('title')}</h1>
        <p className="mb-10 text-sm leading-relaxed">{t('intro', { name: agency.displayName })}</p>
        <dl className="grid gap-6 text-sm">
          {agency.legalLines.map((line) => (
            <div key={line.key}>
              <dt className="text-muted">{t(line.key)}</dt>
              <dd className="mt-1 mb-0">{line.value}</dd>
            </div>
          ))}
          <div>
            <dt className="text-muted">{t('madeBy')}</dt>
            <dd className="mt-1 mb-0">{t('madeByValue')}</dd>
          </div>
        </dl>
        <p className="mt-10 text-sm leading-relaxed">{t('intellectualProperty', { name: agency.displayName })}</p>
      </main>
      <SiteFooter />
    </div>
  )
}
