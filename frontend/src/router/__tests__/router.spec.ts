import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { fakeBackend, type FakeBackend } from '@/__tests__/fakeBackend'
import type { User } from '@/api'
import { makeUser, sessionRoutes, stubBrowser } from '@/views/__tests__/session'
import router from '../index'

// The pages themselves are tested on their own; navigating only needs something to show.
vi.mock('@/views/CalendarView.vue', () => ({ default: { render: () => null } }))
vi.mock('@/views/SettingsView.vue', () => ({ default: { render: () => null } }))
vi.mock('@/views/AccountView.vue', () => ({ default: { render: () => null } }))
vi.mock('@/views/AdminView.vue', () => ({ default: { render: () => null } }))
vi.mock('@/views/NotificationsView.vue', () => ({ default: { render: () => null } }))

let backend: FakeBackend
let start = 0

/** A fresh session (signed in as `user`, or signed out), starting from a page that doesn't care. */
async function session(user: User | null) {
  setActivePinia(createPinia())
  backend = fakeBackend(sessionRoutes(user))
  await router.replace(`/event/start-${start++}`)
}

const visit = async (path: string) => {
  await router.push(path)
  return router.currentRoute.value.fullPath
}

beforeEach(() => {
  stubBrowser()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('router', () => {
  describe('signed out', () => {
    beforeEach(() => session(null))

    it.each(['/', '/calendar', '/calendar/c1', '/notifications', '/calendar/c1/settings', '/account', '/admin'])(
      'sends %s to the login',
      async (path) => {
        expect(await visit(path)).toBe('/login')
      },
    )

    it.each(['/login', '/register', '/forgot-password'])('shows %s', async (path) => {
      expect(await visit(path)).toBe(path)
    })
  })

  describe('signed in', () => {
    beforeEach(() => session(makeUser()))

    it.each(['/login', '/register', '/forgot-password'])('sends %s to the calendar', async (path) => {
      expect(await visit(path)).toBe('/calendar')
    })

    it('opens the calendar at the start page', async () => {
      expect(await visit('/')).toBe('/calendar')
    })

    it.each(['/calendar/c1', '/calendar/folder/f1', '/notifications', '/calendar/c1/settings', '/account'])(
      'shows %s',
      async (path) => {
        expect(await visit(path)).toBe(path)
      },
    )

    it('keeps the administration from users who are no administrators', async () => {
      expect(await visit('/admin')).toBe('/calendar')
    })

    it('restores the session only once', async () => {
      await visit('/account')
      await visit('/notifications')
      expect(backend.calls('GET /api/auth/csrf')).toHaveLength(1)
      expect(backend.calls('GET /api/users/me')).toHaveLength(1)
    })
  })

  it('shows the administration to administrators', async () => {
    await session(makeUser({ is_admin: true }))
    expect(await visit('/admin')).toBe('/admin')
  })

  it('opens invitation links without asking for a session', async () => {
    setActivePinia(createPinia())
    backend = fakeBackend(sessionRoutes(null))
    await router.replace('/event/token-2')
    expect(backend.calls('GET /api/users/me')).toHaveLength(0)
    // Answering posts, which needs the CSRF cookie.
    expect(backend.calls('GET /api/auth/csrf')).toHaveLength(1)
  })

  it.each([null, makeUser()])('shows invitation and password links to anyone (user %#)', async (user) => {
    await session(user)
    expect(await visit('/event/token-1?answer=accepted')).toBe('/event/token-1?answer=accepted')
    // Links in emails sent before the page moved.
    expect(await visit('/rsvp/token-3?answer=declined')).toBe('/event/token-3?answer=declined')
    expect(await visit('/reset-password/key-1')).toBe('/reset-password/key-1')
  })

  it('tells the password page whether its link came with the invitation to a new account', () => {
    const propsOf = (path: string) => {
      const route = router.resolve(path)
      return (route.matched[0]!.props.default as (r: typeof route) => object)(route)
    }
    expect(propsOf('/reset-password/key-1?invite=1')).toEqual({ resetKey: 'key-1', invite: true })
    expect(propsOf('/reset-password/key-1')).toEqual({ resetKey: 'key-1', invite: false })
  })
})
