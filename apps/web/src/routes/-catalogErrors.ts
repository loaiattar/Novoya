import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/errors'
import { type CatalogErrorKey, catalogErrorKey } from '../domain/catalog/catalog'

/**
 * The messages of a partner or offer form, translated: the fields the checks refused, and
 * `form` for a save the API refused. Empty when nothing failed.
 */
export function useCatalogErrors<F extends string>(
  checks: Partial<Record<F, CatalogErrorKey>>,
  saveError: unknown,
): Partial<Record<F | 'form', string>> {
  const { t } = useTranslation('admin')
  const errors: Partial<Record<F | 'form', string>> = {}
  for (const [field, key] of Object.entries(checks) as [F, CatalogErrorKey | undefined][]) {
    if (key) errors[field] = t(key)
  }
  if (saveError) {
    const api = saveError instanceof ApiError ? saveError : undefined
    errors.form = t(catalogErrorKey(api?.status, api?.code))
  }
  return errors
}

/** Thrown to the form when a check fails: the form keeps what was typed and nothing is sent. */
export class RefusedByChecks extends Error {
  constructor() {
    super('Some fields did not pass the checks')
    this.name = 'RefusedByChecks'
  }
}
