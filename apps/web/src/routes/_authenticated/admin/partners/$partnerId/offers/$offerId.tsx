import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  listOffersOptions,
  listOffersQueryKey,
  listPartnersOptions,
  updateOfferMutation,
} from '../../../../../../api/generated/@tanstack/react-query.gen'
import type { OfferResponse, PartnerResponse } from '../../../../../../api/generated/types.gen'
import { Eyebrow } from '../../../../../../components/atoms/Eyebrow'
import { ErrorNote } from '../../../../../../components/molecules/ErrorNote'
import { OfferForm } from '../../../../../../components/organisms/OfferForm'
import {
  offerFormErrors,
  type OfferFormErrors,
  offerFormValues,
  toPatchOfferBody,
} from '../../../../../../domain/catalog/catalog'
import { RefusedByChecks, useCatalogErrors } from '../../../../../-catalogErrors'

export const Route = createFileRoute('/_authenticated/admin/partners/$partnerId/offers/$offerId')({
  component: OfferPage,
})

/** One offer of a partner, to change. Read from the partner's offers. */
function OfferPage() {
  const { partnerId, offerId } = Route.useParams()
  const { t } = useTranslation('admin')
  const partners = useQuery(listPartnersOptions())
  const partner = partners.data?.find((row) => row.id === partnerId)
  const offers = useQuery({ ...listOffersOptions({ query: { partner_id: partnerId } }), enabled: Boolean(partner) })
  const offer = offers.data?.find((row) => row.id === offerId)

  return (
    <>
      {partner ? (
        <Link to="/admin/partners/$partnerId" params={{ partnerId }} className="text-sm underline underline-offset-4">
          {t('offers.backTo', { name: partner.name })}
        </Link>
      ) : (
        <Link to="/admin/partners" className="text-sm underline underline-offset-4">
          {t('partners.back')}
        </Link>
      )}
      {partners.isPending ? (
        <p className="py-6 text-muted">{t('partners.loading')}</p>
      ) : !partners.data ? (
        <ErrorNote message={t('partners.loadFailed')} onRetry={() => partners.refetch()} />
      ) : !partner ? (
        <p className="py-6">{t('partners.notFound')}</p>
      ) : offers.isPending ? (
        <p className="py-6 text-muted">{t('offers.loading')}</p>
      ) : !offers.data ? (
        <ErrorNote message={t('offers.loadFailed')} onRetry={() => offers.refetch()} />
      ) : !offer ? (
        <p className="py-6">{t('offers.notFound')}</p>
      ) : (
        <OfferDetails key={offer.id} partner={partner} offer={offer} />
      )}
    </>
  )
}

function OfferDetails({ partner, offer }: { partner: PartnerResponse; offer: OfferResponse }) {
  const { t } = useTranslation('admin')
  const queryClient = useQueryClient()
  const [checks, setChecks] = useState<OfferFormErrors>({})
  const save = useMutation({
    ...updateOfferMutation(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: listOffersQueryKey() }),
  })
  const errors = useCatalogErrors(checks, save.error)

  return (
    <>
      <Eyebrow className="mt-6">{partner.name}</Eyebrow>
      <h1 className="m-0 mb-8 text-display-s break-words">{offer.title}</h1>
      <OfferForm
        mode="edit"
        imported={partner.imported}
        initialValues={offerFormValues(offer)}
        pending={save.isPending}
        errors={errors}
        success={save.isSuccess ? t('offers.saved') : undefined}
        onSubmit={async (values) => {
          // DÉTOUR owns the offers of an imported partner: only featured and hidden are sent.
          if (partner.imported) {
            setChecks({})
            return save.mutateAsync({
              path: { offer_id: offer.id },
              body: { featured: values.featured, hidden: values.hidden },
            })
          }
          const found = offerFormErrors(values)
          setChecks(found)
          if (Object.keys(found).length > 0) {
            save.reset()
            throw new RefusedByChecks()
          }
          return save.mutateAsync({ path: { offer_id: offer.id }, body: toPatchOfferBody(values) })
        }}
      />
    </>
  )
}
