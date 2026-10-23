import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  listAllExtrasOptions,
  listAllExtrasQueryKey,
  updateExtraMutation,
} from '../../../../api/generated/@tanstack/react-query.gen'
import type { AdminExtraResponse } from '../../../../api/generated/types.gen'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { ErrorNote } from '../../../../components/molecules/ErrorNote'
import { ExtrasTable } from '../../../../components/organisms/ExtrasTable'
import { withId, withoutId } from '../../../../lib/idSet'

// The guard is in ../route.tsx: admins only.
export const Route = createFileRoute('/_authenticated/admin/extras/')({
  component: ExtrasPage,
})

/** Every extra, inactive and hidden ones too. DÉTOUR owns them: only the hidden switch changes. */
function ExtrasPage() {
  const { t } = useTranslation('admin')
  const queryClient = useQueryClient()
  const extras = useQuery(listAllExtrasOptions())
  // Each row's switch is saved on its own, as on the offers table: a success on one row never
  // hides a failure on another.
  const [savingIds, setSavingIds] = useState<ReadonlySet<string>>(new Set())
  const [failedIds, setFailedIds] = useState<ReadonlySet<string>>(new Set())
  const hide = useMutation({
    ...updateExtraMutation(),
    onMutate: ({ path }) => {
      setSavingIds((ids) => withId(ids, path.extra_id))
      setFailedIds((ids) => withoutId(ids, path.extra_id))
    },
    onError: (_error, { path }) => setFailedIds((ids) => withId(ids, path.extra_id)),
    onSuccess: (saved: AdminExtraResponse) =>
      queryClient.setQueryData(listAllExtrasQueryKey(), (rows: AdminExtraResponse[] | undefined) =>
        rows?.map((row) => (row.id === saved.id ? saved : row)),
      ),
    onSettled: (_data, _error, { path }) => setSavingIds((ids) => withoutId(ids, path.extra_id)),
  })

  return (
    <>
      <Eyebrow>{t('eyebrow')}</Eyebrow>
      <h1 className="m-0 text-display-s">{t('extras.title')}</h1>
      <p className="mt-3 mb-8 max-w-[60ch] text-muted">{t('extras.intro')}</p>

      {failedIds.size > 0 && (
        <p role="alert" className="mb-4 text-danger">
          {t('extras.switchFailed')}
        </p>
      )}
      {extras.isPending ? (
        <p className="py-6 text-muted">{t('extras.loading')}</p>
      ) : !extras.data ? (
        <ErrorNote message={t('extras.loadFailed')} onRetry={() => extras.refetch()} />
      ) : extras.data.length === 0 ? (
        <p className="py-6 text-muted">{t('extras.empty')}</p>
      ) : (
        <div className="overflow-x-auto">
          <ExtrasTable
            extras={extras.data}
            savingIds={savingIds}
            onHide={(extraId, hidden) => hide.mutate({ path: { extra_id: extraId }, body: { hidden } })}
          />
        </div>
      )}
    </>
  )
}
