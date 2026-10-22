import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { listPartnersOptions } from '../../../../api/generated/@tanstack/react-query.gen'
import { Button } from '../../../../components/atoms/Button'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { Input } from '../../../../components/atoms/Input'
import { ErrorNote } from '../../../../components/molecules/ErrorNote'
import { PartnersTable } from '../../../../components/organisms/PartnersTable'
import { filterPartners, type PartnerSource } from '../../../../domain/catalog/catalog'

export const Route = createFileRoute('/_authenticated/admin/partners/')({
  component: PartnersPage,
})

const SOURCES: PartnerSource[] = ['all', 'imported', 'manual']

/** Every partner, even inactive or hidden ones. The search and the source filter stay on this page. */
function PartnersPage() {
  const { t } = useTranslation('admin')
  const [search, setSearch] = useState('')
  const [source, setSource] = useState<PartnerSource>('all')
  const partners = useQuery(listPartnersOptions())
  const shown = partners.data ? filterPartners(partners.data, search, source) : []

  return (
    <>
      <Eyebrow>{t('eyebrow')}</Eyebrow>
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <h1 className="m-0 text-[39px] md:text-[50px]">{t('partners.title')}</h1>
        <Button asChild variant="coral" className="self-start md:self-auto">
          <Link to="/admin/partners/new">{t('partners.new')}</Link>
        </Button>
      </div>

      <div className="mt-10 mb-4 flex flex-col gap-2.5 md:flex-row">
        <label className="sr-only" htmlFor="partners-search">
          {t('partners.searchLabel')}
        </label>
        <Input
          id="partners-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t('partners.searchPlaceholder')}
          className="md:max-w-[350px]"
        />
        <label className="sr-only" htmlFor="partners-source">
          {t('partners.sourceFilter')}
        </label>
        <select
          id="partners-source"
          value={source}
          onChange={(event) => setSource(event.target.value as PartnerSource)}
          className="min-h-11 border border-line bg-white px-3"
        >
          {SOURCES.map((value) => (
            <option key={value} value={value}>
              {t(`source.${value}`)}
            </option>
          ))}
        </select>
      </div>

      {partners.isPending ? (
        <p className="py-6 text-muted">{t('partners.loading')}</p>
      ) : !partners.data ? (
        <ErrorNote message={t('partners.loadFailed')} onRetry={() => partners.refetch()} />
      ) : partners.data.length === 0 ? (
        <p className="py-6 text-muted">{t('partners.empty')}</p>
      ) : shown.length === 0 ? (
        <p className="py-6 text-muted">{t('partners.noMatch')}</p>
      ) : (
        <div className="overflow-x-auto">
          <PartnersTable partners={shown} />
        </div>
      )}
    </>
  )
}
