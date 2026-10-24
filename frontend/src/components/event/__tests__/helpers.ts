import { vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { browserTimeZone } from '@/services/datetime'
import { realtime } from '@/services/realtime'
import { useAuthStore } from '@/stores/auth'

export const me = {
  id: 'me',
  email: 'me@example.com',
  display_name: 'Me Myself',
  is_admin: false,
  language: 'en',
  timezone: browserTimeZone(),
  // Dates read the same everywhere: 2026-03-10 09:00.
  date_format: 'ymd',
  time_format: '24h',
} as unknown as api.User

/** Fresh stores with `me` signed in; nothing is sent to the server or opened for it. */
export function signIn(user: api.User | null = me) {
  setActivePinia(createPinia())
  vi.spyOn(realtime, 'start').mockImplementation(() => {})
  vi.spyOn(realtime, 'stop').mockImplementation(() => {})
  i18n.global.locale.value = 'en'
  useAuthStore().user = user
}

export function calendar(role: api.CalendarRole | null = 'owner', extra: Partial<api.Calendar> = {}): api.Calendar {
  return {
    id: 'cal1',
    name: 'Team',
    force_all_day: false,
    my_membership: role ? ({ role, user_id: me.id } as api.CalendarMember) : null,
    ...extra,
  } as api.Calendar
}

export function event(extra: Partial<api.Event> = {}): api.Event {
  return {
    id: 'ev1',
    calendar_id: 'cal1',
    creator_id: me.id,
    creator_name: 'Me Myself',
    creator_email: me.email,
    title: 'Planning',
    description: 'Agenda',
    location: '',
    location_resource_id: null,
    location_resource_name: null,
    start: '2026-03-10T09:00:00.000Z',
    end: '2026-03-10T10:00:00.000Z',
    all_day: false,
    timezone: 'UTC',
    show_recurrence_count: false,
    rrule: null,
    uid: 'uid1',
    parent_id: null,
    recurrence_id: null,
    category_id: null,
    category_name: null,
    category_color: null,
    resource_id: null,
    resource_name: null,
    status: 'approved',
    awaiting_approval: [],
    decided_by: null,
    decided_at: null,
    decision_note: null,
    created_at: '2026-03-01T08:00:00.000Z',
    updated_at: '2026-03-01T08:00:00.000Z',
    ...extra,
  }
}

export function participant(extra: Partial<api.EventParticipant> = {}): api.EventParticipant {
  return {
    id: 'p1',
    event_id: 'ev1',
    user_id: 'u1',
    email: 'anna@example.com',
    display_name: 'Anna',
    status: 'accepted',
    ...extra,
  } as api.EventParticipant
}
