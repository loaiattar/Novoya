import { ApiError } from '../api/errors'

/**
 * The `admin` text for a refused or failed role change (PATCH /admin/users/{id}/role). A refusal
 * that a retry cannot fix gets its own message. Shared by the users and the admins pages.
 */
export function roleErrorKey(error: unknown) {
  const code = error instanceof ApiError ? error.code : undefined
  if (code === 'cannot_change_admin_role') return 'changeRefused.adminRole'
  if (code === 'super_admin_server_only') return 'changeRefused.superAdmin'
  if (code === 'cannot_promote_disabled') return 'changeRefused.disabledAccount'
  if (code === 'email_not_verified') return 'changeRefused.emailNotVerified'
  return 'changeFailed'
}
