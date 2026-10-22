import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  listOffersOptions,
  listOffersQueryKey,
  listPartnersOptions,
  listPartnersQueryKey,
  updateOfferMutation,
  updatePartnerMutation,
} from '../../../../../api/generated/@tanstack/react-query.gen'
import type { OfferResponse, PartnerResponse } from '../../../../../api/generated/types.gen'
import { Button } from '../../../../../components/atoms/Button'
import { Eyebrow } from '../../../../../components/atoms/Eyebrow'
import { ErrorNote } from '../../../../../components/molecules/ErrorNote'
import { OffersTable } from '../../../../../components/organisms/OffersTable'
import { PartnerForm } from '../../../../../components/organisms/PartnerForm'
import {
  partnerFormErrors,
  type PartnerFormErrors,
  partnerFormValues,
  toPatchPartnerBody,
} from '../../../../../domain/catalog/catalog'
import { RefusedByChecks, useCatalogErrors } from '../../../../-catalogErrors'

export const Route = createFileRoute('/_authenticated/admin/partners/$partnerId/')({
  component: PartnerPage,
})

/** One partner: its details to change, then its offers. */
function PartnerPage() {
  const { partnerId } = Route.useParams()
  const { t } = useTranslation('admin')
  // The admin list has every partner: the page reads its partner there (and from its cache).
  const partners = useQuery(listPartnersOptions())
  const partner = partners.data?.find((row) => row.id === partnerId)

  return (
    <>
      <Link to="/admin/partners" className="text-sm underline underline-offset-4">
        {t('partners.back')}
      </Link>
      {partners.isPending ? (
        <p className="py-6 text-muted">{t('partners.loading')}</p>
      ) : !partners.data ? (
        <ErrorNote message={t('partners.loadFailed')} onRetry={() => partners.refetch()} />
      ) : !partner ? (
        <p className="py-6">{t('partners.notFound')}</p>
      ) : (
        <PartnerDetails key={partner.id} partner={partner} />
      )}
    </>
  )
}

function PartnerDetails({ partner }: { partner: PartnerResponse }) {
  const { t } = useTranslation('admin')
  const queryClient = useQueryClient()
  const [checks, setChecks] = useState<PartnerFormErrors>({})
  const save = useMutation({
    ...updatePartnerMutation(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: listPartnersQueryKey() }),
  })
  const errors = useCatalogErrors(checks, save.error)

  return (
    <>
      <Eyebrow className="mt-6">{t('partners.title')}</Eyebrow>
      <h1 className="m-0 mb-8 text-[39px] break-words md:text-[50px]">{partner.name}</h1>
      <PartnerForm
        mode="edit"
        imported={partner.imported}
        initialValues={partnerFormValues(partner)}
        pending={save.isPending}
        errors={errors}
        success={save.isSuccess ? t('partners.saved') : undefined}
        onSubmit={async (values) => {
          // DÉTOUR owns an imported partner: only its hidden switch is sent.
          if (partner.imported) {
            setChecks({})
            return save.mutateAsync({ path: { partner_id: partner.id }, body: { hidden: values.hidden } })
          }
          const found = partnerFormErrors(values)
          setChecks(found)
          if (Object.keys(found).length > 0) {
            save.reset()
            throw new RefusedByChecks()
          }
          return save.mutateAsync({ path: { partner_id: partner.id }, body: toPatchPartnerBody(values) })
        }}
      />
      <PartnerOffers partner={partner} />
    </>
  )
}

function PartnerOffers({ partner }: { partner: PartnerResponse }) {
  const { t } = useTranslation('admin')
  const queryClient = useQueryClient()
  const options = { query: { partner_id: partner.id } }
  const offers = useQuery(listOffersOptions(options))
  // Each row's switch is saved on its own: track which rows wait and which failed, so a
  // success on one row never hides a failure on another.
  const [savingIds, setSavingIds] = useState<ReadonlySet<string>>(new Set())
  const [failedIds, setFailedIds] = useState<ReadonlySet<string>>(new Set())
  const toggle = useMutation({
    ...updateOfferMutation(),
    onMutate: ({ path }) => {
      setSavingIds((ids) => withId(ids, path.offer_id))
      setFailedIds((ids) => withoutId(ids, path.offer_id))
    },
    onError: (_error, { path }) => setFailedIds((ids) => withId(ids, path.offer_id)),
    onSuccess: (saved: OfferResponse) => {
      queryClient.setQueryData(listOffersQueryKey(options), (rows: OfferResponse[] | undefined) =>
        rows?.map((row) => (row.id === saved.id ? saved : row)),
      )
      return queryClient.invalidateQueries({ queryKey: listOffersQueryKey() })
    },
    onSettled: (_data, _error, { path }) => setSavingIds((ids) => withoutId(ids, path.offer_id)),
  })

  return (
    <section aria-labelledby="partner-offers" className="mt-14">
      <div className="mb-4 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <h2 id="partner-offers" className="m-0 text-[28px]">
          {t('offers.title')}
        </h2>
        {!partner.imported && (
          <Button asChild variant="coral" className="self-start md:self-auto">
            <Link to="/admin/partners/$partnerId/offers/new" params={{ partnerId: partner.id }}>
              {t('offers.new')}
            </Link>
          </Button>
        )}
      </div>
      {failedIds.size > 0 && (
        <p role="alert" className="mb-4 text-danger">
          {t('offers.switchFailed')}
        </p>
      )}
      {offers.isPending ? (
        <p className="py-6 text-muted">{t('offers.loading')}</p>
      ) : !offers.data ? (
        <ErrorNote message={t('offers.loadFailed')} onRetry={() => offers.refetch()} />
      ) : offers.data.length === 0 ? (
        <p className="py-6 text-muted">{partner.imported ? t('offers.importedNoNew') : t('offers.empty')}</p>
      ) : (
        <div className="overflow-x-auto">
          <OffersTable
            caption={t('offers.table.caption', { name: partner.name })}
            partnerId={partner.id}
            offers={offers.data}
            savingIds={savingIds}
            onSwitch={(offerId, field, value) =>
              toggle.mutate({ path: { offer_id: offerId }, body: { [field]: value } })
            }
          />
        </div>
      )}
    </section>
  )
}

function withId(ids: ReadonlySet<string>, id: string): ReadonlySet<string> {
  return new Set(ids).add(id)
}

function withoutId(ids: ReadonlySet<string>, id: string): ReadonlySet<string> {
  const next = new Set(ids)
  next.delete(id)
  return next
}
