import type { CalendarRole } from '@/api'

/** Calendar roles from the least to the most privileged; each allows what the ones before it do. */
export const ROLE_ORDER: CalendarRole[] = ['read', 'own', 'full', 'manage', 'owner']

/** Whether `role` allows at least what `atLeast` does; no role (no access) allows nothing. */
export function hasRole(role: CalendarRole | null | undefined, atLeast: CalendarRole): boolean {
  return !!role && ROLE_ORDER.indexOf(role) >= ROLE_ORDER.indexOf(atLeast)
}
