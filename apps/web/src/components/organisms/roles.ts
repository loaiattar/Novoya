export type Role = 'client' | 'agent' | 'admin' | 'super_admin'

/** The roles, in the order the admin page lists them. Their names are in the `admin` namespace. */
export const ROLES: Role[] = ['client', 'agent', 'admin', 'super_admin']

/** The roles the users page can give. The super admin role is given on the server only. */
export const GIVEN_ROLES: Role[] = ['client', 'agent', 'admin']

/** The roles that only a super admin gives, takes or acts on (same rule as the API). */
export function isAdminRole(role: Role): boolean {
  return role === 'admin' || role === 'super_admin'
}

/**
 * Whether a user is out of the viewer's reach: nobody acts on a super admin here (the server
 * command manages them), and only a super admin acts on admins. Same rule as the API.
 */
export function adminOutOfReach(target: Role, viewer: Role): boolean {
  return target === 'super_admin' || (viewer !== 'super_admin' && isAdminRole(target))
}

/** The account facts the role rules look at. */
export type RoleTarget = { status: 'active' | 'disabled'; email_verified: boolean }

/**
 * Whether the viewer may give this role to a user. The super admin role is given on the server
 * only, only a super admin gives the admin role, and a disabled account or an unverified email
 * stays a client. Same rules as the API (accounts/domain/user.py).
 */
export function canGiveRole(role: Role, target: RoleTarget, viewer: Role): boolean {
  return (
    role !== 'super_admin' &&
    (role === 'client' || (target.status === 'active' && target.email_verified)) &&
    (viewer === 'super_admin' || !isAdminRole(role))
  )
}
