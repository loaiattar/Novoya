import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { createPartnerMutation, listPartnersQueryKey } from '../../../../api/generated/@tanstack/react-query.gen'
import type { PartnerResponse } from '../../../../api/generated/types.gen'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { PartnerForm } from '../../../../components/organisms/PartnerForm'
import {
  NEW_PARTNER,
  partnerFormErrors,
  type PartnerFormErrors,
  toCreatePartnerBody,
} from '../../../../domain/catalog/catalog'
import { RefusedByChecks, useCatalogErrors } from '../../../-catalogErrors'

export const Route = createFileRoute('/_authenticated/admin/partners/new')({
  component: NewPartnerPage,
})

function NewPartnerPage() {
  const { t } = useTranslation('admin')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [checks, setChecks] = useState<PartnerFormErrors>({})
  const create = useMutation(createPartnerMutation())
  const errors = useCatalogErrors(checks, create.error)

  return (
    <>
      <Link to="/admin/partners" className="text-sm underline underline-offset-4">
        {t('partners.back')}
      </Link>
      <Eyebrow className="mt-6">{t('partners.title')}</Eyebrow>
      <h1 className="m-0 mb-8 text-[39px] md:text-[50px]">{t('partners.new')}</h1>
      <PartnerForm
        mode="create"
        initialValues={NEW_PARTNER}
        pending={create.isPending}
        errors={errors}
        onSubmit={async (values) => {
          const found = partnerFormErrors(values)
          setChecks(found)
          if (Object.keys(found).length > 0) {
            create.reset()
            throw new RefusedByChecks()
          }
          const partner = await create.mutateAsync({ body: toCreatePartnerBody(values) })
          // The partner page reads the list: it has the new partner even if reading it again fails.
          queryClient.setQueryData(listPartnersQueryKey(), (rows: PartnerResponse[] | undefined) => [
            ...(rows ?? []).filter((row) => row.id !== partner.id),
            partner,
          ])
          await queryClient.invalidateQueries({ queryKey: listPartnersQueryKey() })
          await navigate({ to: '/admin/partners/$partnerId', params: { partnerId: partner.id } })
        }}
      />
    </>
  )
}
