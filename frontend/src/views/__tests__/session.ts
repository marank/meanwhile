import { vi } from 'vitest'
import type { AppNotification, User } from '@/api'
import { browserTimeZone } from '@/services/datetime'
import { realtime } from '@/services/realtime'

/** A signed-in user whose zone and language already match, so the auth store doesn't update the profile. */
export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'u1',
    email: 'alice@example.com',
    display_name: 'Alice Smith',
    is_admin: false,
    is_active: true,
    time_format: '24h',
    date_format: 'ymd',
    timezone: browserTimeZone(),
    language: 'en',
    ...overrides,
  } as User
}

export function makeNotification(overrides: Partial<AppNotification> = {}): AppNotification {
  return {
    id: 'n1',
    type: 'participant_added',
    actor_id: 'u2',
    actor_name: 'Bob',
    calendar_id: 'c1',
    event_id: 'e1',
    title: 'Standup',
    data: null,
    read_at: null,
    created_at: '2026-01-05T09:00:00',
    event_status: null,
    response_status: null,
    deletable: false,
    link: '/event/e1',
    ...overrides,
  }
}

/** The routes the auth store asks for when restoring a session; `user` null means signed out. */
export function sessionRoutes(user: User | null) {
  return {
    'GET /api/auth/csrf': { ok: true },
    'GET /api/users/me': user ?? new Response(null, { status: 401 }),
  }
}

/** What jsdom lacks and the navbar needs; the live connection is never opened. */
export function stubBrowser() {
  const observers: Array<{ callback: ResizeObserverCallback }> = []
  vi.stubGlobal(
    'ResizeObserver',
    class {
      callback: ResizeObserverCallback
      constructor(callback: ResizeObserverCallback) {
        this.callback = callback
        observers.push(this)
      }
      observe() {}
      disconnect() {}
    },
  )
  vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} }))
  vi.spyOn(realtime, 'start').mockImplementation(() => {})
  vi.spyOn(realtime, 'stop').mockImplementation(() => {})
  return { observers }
}
