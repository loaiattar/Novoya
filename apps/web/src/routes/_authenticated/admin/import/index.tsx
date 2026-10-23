import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import type { TFunction } from 'i18next'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../../../api/errors'
import {
  getImportLimitsOptions,
  importDetourMutation,
} from '../../../../api/generated/@tanstack/react-query.gen'
import { Button } from '../../../../components/atoms/Button'
import { Eyebrow } from '../../../../components/atoms/Eyebrow'
import { Field } from '../../../../components/molecules/Field'

// The names a sqlite file goes by. The API checks the file's header, not its name.
const EXTENSIONS = ['.sqlite', '.sqlite3', '.db']

export const Route = createFileRoute('/_authenticated/admin/import/')({
  component: ImportPage,
})

/** An admin uploads a new DÉTOUR export and imports it, as the command line does. */
function ImportPage() {
  const { t } = useTranslation('admin')
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string>()
  // The API's own limit (NOVOYA_DETOUR_MAX_BYTES), checked here to answer at once. Until it
  // is known, the API's 413 is the only check.
  const limits = useQuery(getImportLimitsOptions())
  const maxBytes = limits.data?.max_bytes
  const maxMb = maxBytes === undefined ? undefined : Math.floor(maxBytes / 1_000_000)
  const importing = useMutation({
    ...importDetourMutation(),
    // Partners, offers, reviews, extras and destinations may all have changed.
    onSuccess: () => queryClient.invalidateQueries(),
  })

  function choose(chosen: File | undefined) {
    importing.reset()
    setFile(null)
    setFileError(undefined)
    if (!chosen) return
    const name = chosen.name.toLowerCase()
    if (!EXTENSIONS.some((extension) => name.endsWith(extension))) setFileError(t('import.errors.notSqlite'))
    else if (maxBytes !== undefined && chosen.size > maxBytes) setFileError(tooLarge(t, maxMb))
    else setFile(chosen)
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (file) importing.mutate({ body: file })
  }

  return (
    <>
      <Eyebrow>{t('eyebrow')}</Eyebrow>
      <h1 className="m-0 text-display-s">{t('import.title')}</h1>
      <p className="mt-4 max-w-2xl text-muted">{t('import.intro')}</p>
      <form onSubmit={submit} className="mt-8 max-w-xl">
        <Field
          label={t('import.file')}
          hint={maxMb === undefined ? t('import.fileHintNoLimit') : t('import.fileHint', { max: maxMb })}
          error={fileError}
        >
          {({ id, describedBy, invalid }) => (
            <input
              id={id}
              type="file"
              accept={EXTENSIONS.join(',')}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              disabled={importing.isPending}
              onChange={(event) => choose(event.target.files?.[0])}
              className="block w-full border border-line bg-white px-4 py-3.5 text-base text-ink file:mr-4 file:rounded-full file:border-0 file:bg-ivory file:px-4 file:py-2 file:font-semibold aria-invalid:border-danger"
            />
          )}
        </Field>
        <Button type="submit" disabled={!file || importing.isPending}>
          {importing.isPending ? t('import.importing') : t('import.submit')}
        </Button>
      </form>
      {importing.isSuccess && (
        <section role="status" className="mt-8 max-w-xl border border-line bg-white p-6">
          <h2 className="m-0 text-xl">{t('import.done')}</h2>
          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
            {(['partners', 'offers', 'reviews', 'extras'] as const).map((kind) => (
              <div key={kind}>
                <dt className="text-sm text-muted">{t(`import.counts.${kind}`)}</dt>
                <dd className="m-0 text-2xl font-semibold">{importing.data[kind]}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      {importing.isError && (
        <p role="alert" className="mt-8 max-w-xl text-danger">
          {errorMessage(importing.error, t, maxMb)}
        </p>
      )}
    </>
  )
}

function tooLarge(t: TFunction<'admin'>, maxMb: number | undefined): string {
  return maxMb === undefined ? t('import.errors.tooLargeNoLimit') : t('import.errors.tooLarge', { max: maxMb })
}

function errorMessage(error: unknown, t: TFunction<'admin'>, maxMb: number | undefined): string {
  if (!(error instanceof ApiError)) return t('import.errors.unknown')
  // A proxy in front of the API may answer 413 itself, without our error body.
  if (error.status === 413) return tooLarge(t, maxMb)
  if (error.code === 'not_a_detour_export') return t('import.errors.notSqlite')
  if (error.code === 'detour_import_failed') return t('import.errors.failed', { detail: error.message })
  if (error.code === 'import_running') return t('import.errors.running')
  return t('import.errors.unknown')
}
