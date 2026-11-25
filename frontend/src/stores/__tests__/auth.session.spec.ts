import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import { i18n } from '@/i18n'
import { browserTimeZone } from '@/services/datetime'
import { realtime } from '@/services/realtime'
import { useAuthStore } from '../auth'
import { useCalendarStore } from '../calendars'
import { useNotificationsStore } from '../notifications'

const user = (extra: Record<string, unknown> = {}) => ({
  id: 'u1',
  email: 'a@example.com',
  display_name: 'Ada',
  is_admin: false,
  timezone: browserTimeZone(),
  language: 'en',
  ...extra,
})

describe('auth store session', () => {
  let backend: FakeBackend

  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    vi.spyOn(realtime, 'start').mockImplementation(() => {})
    vi.spyOn(realtime, 'stop').mockImplementation(() => {})
    backend = fakeBackend({
      'GET /api/auth/csrf': { ok: true },
      'GET /api/users/me': user(),
      'POST /api/auth/v1/auth/login': { status: 200, data: { user: user() } },
      'POST /api/auth/v1/auth/signup': { status: 200, data: { user: user({ display_name: 'New' }) } },
      'DELETE /api/auth/v1/auth/session': reply(401),
      'PATCH /api/users/me': (r) => user(r.body as Record<string, unknown>),
    })
  })

  afterEach(() => {
    useAuthStore().$dispose()
    vi.restoreAllMocks()
  })

  it('restores the session once, and connects live while signed in', async () => {
    const store = useAuthStore()
    await Promise.all([store.init(), store.init()])
    expect(backend.calls('GET /api/users/me')).toHaveLength(1)
    expect(store.isLoggedIn).toBe(true)
    expect(store.isAdmin).toBe(false)
    expect(realtime.start).toHaveBeenCalled()
  })

  it('is signed out when there is no session', async () => {
    backend.on('GET /api/users/me', reply(401))
    const store = useAuthStore()
    await store.init()
    expect(store.isLoggedIn).toBe(false)
  })

  it('signs up and in', async () => {
    const store = useAuthStore()
    await store.register('a@example.com', 'New', 'secret')
    expect(store.user?.display_name).toBe('New')
    await store.login('a@example.com', 'secret')
    expect(store.user?.display_name).toBe('Ada')
  })

  it("tells the server the browser's time zone, and its language to an account without one", async () => {
    backend.on('POST /api/auth/v1/auth/login', {
      status: 200,
      data: { user: user({ timezone: null, language: '' }) },
    })
    const store = useAuthStore()
    await store.login('a@example.com', 'secret')
    await vi.waitFor(() => expect(store.user?.language).toBe('en'))
    expect(backend.calls('PATCH /api/users/me')[0]!.body).toEqual({ timezone: browserTimeZone(), language: 'en' })
  })

  it("speaks the account's language, not the one the browser had from someone before", async () => {
    i18n.global.locale.value = 'de-informal'
    backend.on('POST /api/auth/v1/auth/login', { status: 200, data: { user: user({ language: 'de' }) } })
    const store = useAuthStore()
    await store.login('a@example.com', 'secret')
    await vi.waitFor(() => expect(i18n.global.locale.value).toBe('de'))
    expect(localStorage.getItem('locale')).toBe('de')
    expect(backend.calls('PATCH /api/users/me')).toHaveLength(0)
  })

  it('stays signed in when telling the server the language fails', async () => {
    backend.on('POST /api/auth/v1/auth/login', { status: 200, data: { user: user({ language: '' }) } })
    backend.on('PATCH /api/users/me', reply(500))
    const store = useAuthStore()
    await store.login('a@example.com', 'secret')
    await vi.waitFor(() => expect(backend.calls('PATCH /api/users/me')).toHaveLength(1))
    expect(store.user?.language).toBe('')
  })

  it('updates the profile', async () => {
    const store = useAuthStore()
    await store.login('a@example.com', 'secret')
    await store.updateProfile({ display_name: 'Grace' })
    expect(store.user?.display_name).toBe('Grace')
  })

  it('forgets everything loaded for the user on sign out, even if the server call fails', async () => {
    backend.on('GET /api/layout', { folders: [], calendars: [] })
    const store = useAuthStore()
    await store.login('a@example.com', 'secret')
    const calendars = useCalendarStore()
    await calendars.load()
    useNotificationsStore().unreadCount = 3

    await store.logout()
    expect(store.isLoggedIn).toBe(false)
    expect(calendars.loaded).toBe(false)
    expect(useNotificationsStore().unreadCount).toBe(0)
    await vi.waitFor(() => expect(realtime.stop).toHaveBeenCalled())

    // The next sign-in fetches a new CSRF token.
    await store.init()
    expect(backend.calls('GET /api/auth/csrf')).toHaveLength(1)
  })
})
