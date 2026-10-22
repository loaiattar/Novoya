export type Role = 'client' | 'agent' | 'admin' | 'super_admin'

/** The roles, in the order the admin page lists them. Their names are in the `admin` namespace. */
export const ROLES: Role[] = ['client', 'agent', 'admin', 'super_admin']

/** The roles the users page can give. The super admin role is given on the server only. */
export const GIVEN_ROLES: Role[] = ['client', 'agent', 'admin']

/** The roles that only a super admin gives, takes or acts on (same rule as the API). */
export function isAdminRole(role: Role): boolean {
  return role === 'admin' || role === 'super_admin'
}
