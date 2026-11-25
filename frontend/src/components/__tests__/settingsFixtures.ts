// Shared data and helpers for the specs of the settings pages (calendar, account and admin).
import { flushPromises, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import type * as api from '@/api'
import { paletteColors, calendarColorPalettes } from '@/services/calendarColors'
import { dialog, submitDialog } from '@/services/dialog'
import { toasts } from '@/services/toast'

export const appColors = paletteColors(calendarColorPalettes[0]!)

export function calendar(overrides: Partial<api.Calendar> = {}): api.Calendar {
  return {
    id: 'cal',
    name: 'Team',
    description: '',
    url_path: null,
    force_all_day: false,
    first_weekday: 1,
    show_weekends: true,
    weekend_days: [0, 6],
    show_week_numbers: false,
    ...appColors,
    owner_id: 'ann',
    is_public: false,
    public_role: 'read',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    my_membership: member('ann', 'Ann', 'owner'),
    ...overrides,
  }
}

export function member(userId: string, name: string, role: api.CalendarRole): api.CalendarMember {
  return {
    id: `m-${userId}`,
    calendar_id: 'cal',
    user_id: userId,
    email: `${userId}@example.test`,
    display_name: name,
    role,
    folder_id: null,
    position: 0,
  }
}

export function user(overrides: Partial<api.User> = {}): api.User {
  return {
    id: 'ann',
    email: 'ann@example.test',
    display_name: 'Ann',
    is_admin: true,
    is_active: true,
    time_format: 'auto',
    date_format: 'auto',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: 'en',
    day_start: 9,
    email_notifications: {
      invitations: true,
      responses: true,
      approvals: true,
      decisions: true,
      comments: true,
      memberships: true,
      role_changes: false,
      reminders: true,
    },
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

export function searchResult(id: string, label: string, subtitle: string | null = null): api.SearchResult {
  return { id, type: 'user', label, subtitle, meta: null }
}

/** The texts of the toasts shown so far. */
export function toastTexts(): string[] {
  return toasts.map((t) => t.message)
}

export function clearToasts() {
  toasts.splice(0)
}

/** Answers the confirmation that is open (or about to open) and waits for what follows. */
export async function answerConfirm(yes: boolean) {
  await flushPromises()
  if (!dialog.open) throw new Error('No confirmation was asked for')
  submitDialog(yes)
  await flushPromises()
}

/** Finds a button by its text or accessible label. */
export function buttonNamed(root: VueWrapper | DOMWrapper<Element>, name: string): DOMWrapper<HTMLButtonElement> {
  const found = root.findAll('button').find((b) => b.text() === name || b.attributes('aria-label') === name)
  if (!found) throw new Error(`No button named ${name}`)
  return found
}
