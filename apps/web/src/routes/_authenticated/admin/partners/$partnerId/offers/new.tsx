import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  createOfferMutation,
  listOffersQueryKey,
  listPartnersOptions,
} from '../../../../../../api/generated/@tanstack/react-query.gen'
import type { PartnerResponse } from '../../../../../../api/generated/types.gen'
import { Eyebrow } from '../../../../../../components/atoms/Eyebrow'
import { ErrorNote } from '../../../../../../components/molecules/ErrorNote'
import { OfferForm } from '../../../../../../components/organisms/OfferForm'
import {
  newOfferFormValues,
  offerFormErrors,
  type OfferFormErrors,
  toCreateOfferBody,
} from '../../../../../../domain/catalog/catalog'
import { RefusedByChecks, useCatalogErrors } from '../../../../../-catalogErrors'

export const Route = createFileRoute('/_authenticated/admin/partners/$partnerId/offers/new')({
  component: NewOfferPage,
})

/** A new offer for a partner added by hand. An imported partner gets its offers from DÉTOUR. */
function NewOfferPage() {
  const { partnerId } = Route.useParams()
  const { t } = useTranslation('admin')
  const partners = useQuery(listPartnersOptions())
  const partner = partners.data?.find((row) => row.id === partnerId)

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
      ) : partner.imported ? (
        <p className="py-6">{t('offers.importedNoNew')}</p>
      ) : (
        <NewOffer partner={partner} />
      )}
    </>
  )
}

function NewOffer({ partner }: { partner: PartnerResponse }) {
  const { t } = useTranslation('admin')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [checks, setChecks] = useState<OfferFormErrors>({})
  const create = useMutation(createOfferMutation())
  const errors = useCatalogErrors(checks, create.error)

  return (
    <>
      <Eyebrow className="mt-6">{partner.name}</Eyebrow>
      <h1 className="m-0 mb-8 text-display-s">{t('offers.new')}</h1>
      <OfferForm
        mode="create"
        initialValues={newOfferFormValues(partner)}
        pending={create.isPending}
        errors={errors}
        onSubmit={async (values) => {
          const found = offerFormErrors(values)
          setChecks(found)
          if (Object.keys(found).length > 0) {
            create.reset()
            throw new RefusedByChecks()
          }
          await create.mutateAsync({ body: toCreateOfferBody(partner.id, values) })
          await queryClient.invalidateQueries({ queryKey: listOffersQueryKey() })
          await navigate({ to: '/admin/partners/$partnerId', params: { partnerId: partner.id } })
        }}
      />
    </>
  )
}
