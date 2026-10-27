export interface User {
  subject: string
  tenant_id: string
  roles: string[]
}

// Mirrors the backend's _MANAGE_ANY_ROLES. UX gating only — the API authorizes.
const MANAGE_ANY_ROLES = ['tenant_admin', 'platform_admin']

export function isOwnTask(user: User, ownerId: string): boolean {
  return user.subject === ownerId
}

export function canManageTask(user: User, ownerId: string): boolean {
  return isOwnTask(user, ownerId) || user.roles.some((r) => MANAGE_ANY_ROLES.includes(r))
}

/** Short display form of a user id: "You" for the current user. */
export function ownerLabel(user: User, ownerId: string): string {
  return isOwnTask(user, ownerId) ? 'You' : ownerId.slice(0, 8)
}
