import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/errors'
import { accountError, invalidInputFieldErrors, type AccountErrorField } from '../domain/auth/errors'

type AccountErrors = Partial<Record<AccountErrorField | 'form', string>>

/**
 * The message of a failed account request (sign-up, reset, change of password), translated,
 * under the field it belongs to, or `form` for the others. Empty without an error.
 */
export function useAccountErrors(error: unknown): AccountErrors {
  const { t } = useTranslation('errors')
  if (!error) return {}
  if (error instanceof ApiError && error.code === 'invalid_input') {
    const fields = invalidInputFieldErrors(error.message)
    if (Object.keys(fields).length > 0) {
      return Object.fromEntries(
        Object.entries(fields).map(([field, key]) => [field, t(key)]),
      ) as AccountErrors
    }
  }
  const { key, field } = accountError(error instanceof ApiError ? error.code : undefined)
  return { [field ?? 'form']: t(key) }
}
