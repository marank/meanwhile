import type { CalendarRole } from '@/api'
import { allValues } from '@/utils/enums'

/** Calendar roles from the least to the most privileged; each allows what the ones before it do. */
export const ROLE_ORDER = allValues<CalendarRole>({ read: true, own: true, full: true, manage: true, owner: true })

/** Whether `role` allows at least what `atLeast` does; no role (no access) allows nothing. */
export function hasRole(role: CalendarRole | null | undefined, atLeast: CalendarRole): boolean {
  return !!role && ROLE_ORDER.indexOf(role) >= ROLE_ORDER.indexOf(atLeast)
}
