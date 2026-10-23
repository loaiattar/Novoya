import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../../../api/errors'
import {
  listAdvisorsQueryKey,
  listAgentAdvisorsOptions,
  listAgentAdvisorsQueryKey,
  updateAdvisorProfileMutation,
} from '../../../../api/generated/@tanstack/react-query.gen'
import type { AgentAdvisorResponse } from '../../../../api/generated/types.gen'
import { Button } from '../../../../components/atoms/Button'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { ErrorNote } from '../../../../components/molecules/ErrorNote'
import { AdvisorForm, type AdvisorFields } from '../../../../components/organisms/AdvisorForm'

// The guard is in ../route.tsx: admins only.
export const Route = createFileRoute('/_authenticated/admin/advisors/')({
  component: AdvisorsPage,
})

function fieldsOf(row: AgentAdvisorResponse): AdvisorFields {
  const profile = row.profile
  return {
    publicName: profile?.public_name ?? row.name ?? '',
    title: profile?.title ?? '',
    summary: profile?.summary ?? '',
    services: (profile?.services ?? []).map((s) => ({ fr: s.fr ?? '', en: s.en ?? '' })),
    consent: profile?.consent ?? false,
    shown: profile?.shown ?? false,
  }
}

function blankToNull(value: string): string | null {
  return value.trim() === '' ? null : value.trim()
}

type ErrorKey =
  | 'advisors.errors.consentRequired'
  | 'advisors.errors.notAnAgent'
  | 'advisors.errors.invalid'
  | 'advisors.errors.saveFailed'

function errorKey(error: unknown): ErrorKey {
  const code = error instanceof ApiError ? error.code : undefined
  if (code === 'advisor_consent_required') return 'advisors.errors.consentRequired'
  if (code === 'not_an_agent') return 'advisors.errors.notAnAgent'
  if (code === 'invalid_input' || code === 'invalid_advisor_profile') return 'advisors.errors.invalid'
  return 'advisors.errors.saveFailed'
}

/** The agents and what the home page shows of them, with the agent's agreement. */
function AdvisorsPage() {
  const { t } = useTranslation('admin')
  const queryClient = useQueryClient()
  const agents = useQuery(listAgentAdvisorsOptions())
  const [editing, setEditing] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const save = useMutation({
    ...updateAdvisorProfileMutation(),
    onSuccess: (row: AgentAdvisorResponse) => {
      queryClient.setQueryData(listAgentAdvisorsQueryKey(), (rows: AgentAdvisorResponse[] | undefined) =>
        rows?.map((current) => (current.user_id === row.user_id ? row : current)),
      )
      void queryClient.invalidateQueries({ queryKey: listAdvisorsQueryKey() })
      setEditing(null)
      setSaved(row.user_id)
    },
  })

  return (
    <>
      <Eyebrow>{t('eyebrow')}</Eyebrow>
      <h1 className="m-0 text-display-s">{t('advisors.title')}</h1>
      <p className="mt-3 mb-8 max-w-[60ch] text-muted">{t('advisors.intro')}</p>

      {agents.isPending ? (
        <p className="py-6 text-muted">{t('advisors.loading')}</p>
      ) : !agents.data ? (
        <ErrorNote message={t('advisors.loadFailed')} onRetry={() => agents.refetch()} />
      ) : agents.data.length === 0 ? (
        <p className="py-6 text-muted">{t('advisors.empty')}</p>
      ) : (
        <ul className="m-0 grid list-none gap-4 p-0">
          {agents.data.map((row) => {
            const status = !row.profile
              ? 'notFilled'
              : row.profile.shown
                ? 'shown'
                : row.profile.consent
                  ? 'hidden'
                  : 'noConsent'
            const titleId = `advisor-${row.user_id}`
            return (
              <li key={row.user_id} aria-labelledby={titleId} className="border border-line bg-white p-5 md:p-6">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 id={titleId} className="m-0 text-[24px] break-words">
                      {row.profile?.public_name ?? row.name ?? row.email}
                    </h2>
                    <p className="mt-1 mb-0 text-sm break-all text-muted">{row.email}</p>
                    <p className="mt-2 mb-0 text-sm">
                      {t(`advisors.status.${status}`)}
                      {row.status === 'disabled' && ` · ${t('advisors.status.disabled')}`}
                    </p>
                  </div>
                  {editing !== row.user_id && (
                    <Button
                      variant="outline"
                      onClick={() => {
                        save.reset()
                        setSaved(null)
                        setEditing(row.user_id)
                      }}
                    >
                      {t('advisors.edit')}
                    </Button>
                  )}
                </div>
                {saved === row.user_id && (
                  <p role="status" className="mt-3 mb-0 text-sm">
                    {t('advisors.saved')}
                  </p>
                )}
                {editing === row.user_id && (
                  <div className="mt-6">
                    <AdvisorForm
                      initialValues={fieldsOf(row)}
                      pending={save.isPending}
                      error={save.isError ? t(errorKey(save.error)) : undefined}
                      onCancel={() => setEditing(null)}
                      onSubmit={(values) =>
                        save.mutateAsync({
                          path: { user_id: row.user_id },
                          body: {
                            public_name: values.publicName.trim(),
                            title: blankToNull(values.title),
                            summary: blankToNull(values.summary),
                            services: values.services.map((s) => ({ fr: blankToNull(s.fr), en: blankToNull(s.en) })),
                            consent: values.consent,
                            shown: values.shown,
                          },
                        })
                      }
                    />
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </>
  )
}
