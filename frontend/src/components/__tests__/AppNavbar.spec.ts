import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import type { User } from '@/api'
import { i18n } from '@/i18n'
import { sidebarDrawerOpen } from '@/services/sidebarState'
import { toasts } from '@/services/toast'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { makeNotification, makeUser, sessionRoutes, stubBrowser } from '@/views/__tests__/session'
import AppNavbar from '../AppNavbar.vue'

let wrapper: VueWrapper
let router: Router
let backend: FakeBackend
let browser: ReturnType<typeof stubBrowser>

async function render(user: User = makeUser(), counts = { unread: 0, approvals: 0, invitations: 0 }) {
  backend = fakeBackend({
    ...sessionRoutes(user),
    'GET /api/settings': { app_name: 'Team Calendar', logo_url: '', favicon_url: '' },
    'GET /api/notifications/counts': counts,
    'GET /api/notifications': [],
  })
  await useAuthStore().init()
  const page = { template: '<div />' }
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      '/',
      '/notifications',
      '/event/:eventId',
      '/invitation/:token',
      '/calendar/:calendarId',
      '/account',
      '/admin',
      '/login',
    ].map((path) => ({ path, component: page })),
  })
  await router.push('/')
  wrapper = mount(AppNavbar, { global: { plugins: [i18n, router] }, attachTo: document.body })
  await flushPromises()
}

const button = (label: string) => wrapper.get(`button[aria-label="${label}"]`)
const textButton = (text: string) => wrapper.findAll('button').find((b) => b.text() === text)!

beforeEach(() => {
  i18n.global.locale.value = 'en'
  setActivePinia(createPinia())
  browser = stubBrowser()
  toasts.splice(0)
  sidebarDrawerOpen.value = false
})

afterEach(() => {
  wrapper.unmount()
  vi.restoreAllMocks()
})

describe('AppNavbar', () => {
  it("shows the user's name, address and initials", async () => {
    await render()
    expect(wrapper.text()).toContain('Alice Smith')
    expect(wrapper.text()).toContain('alice@example.com')
    expect(wrapper.text()).toContain('AS')
  })

  it("takes the initials from the address when there's no name", async () => {
    await render(makeUser({ display_name: '', email: 'zed@example.com' }))
    expect(wrapper.text()).toContain('Z')
  })

  it('shows how many notifications are unread, at most 9+', async () => {
    await render(makeUser(), { unread: 3, approvals: 0, invitations: 0 })
    expect(wrapper.text()).toContain('3')
    wrapper.unmount()
    setActivePinia(createPinia())
    await render(makeUser(), { unread: 12, approvals: 0, invitations: 0 })
    expect(wrapper.text()).toContain('9+')
  })

  it('opens and closes the sidebar drawer', async () => {
    await render()
    await button('Show calendars').trigger('click')
    expect(sidebarDrawerOpen.value).toBe(true)
    expect(button('Show calendars').attributes('aria-expanded')).toBe('true')
  })

  it('tells the page how tall the navbar is while it is shown', async () => {
    await render()
    const entry = { borderBoxSize: [{ blockSize: 56 }] } as unknown as ResizeObserverEntry
    browser.observers[0]!.callback([entry], {} as ResizeObserver)
    expect(document.documentElement.style.getPropertyValue('--navbar-height')).toBe('56px')
    wrapper.unmount()
    expect(document.documentElement.style.getPropertyValue('--navbar-height')).toBe('')
  })

  it('switches between light and dark', async () => {
    await render()
    expect(button('Toggle dark mode').get('svg').classes().join(' ')).toContain('moon')
    await button('Toggle dark mode').trigger('click')
    expect(button('Toggle dark mode').get('svg').classes().join(' ')).toContain('sun')
  })

  describe('notifications dropdown', () => {
    it('says so when there are no notifications', async () => {
      await render()
      await button('Notifications').trigger('click')
      // Placeholders until the list is there.
      expect(wrapper.find('[data-loading]').exists()).toBe(true)
      await flushPromises()
      expect(wrapper.find('[data-loading]').exists()).toBe(false)
      expect(wrapper.text()).toContain('All caught up')
      expect(wrapper.text()).toContain('No notifications yet.')
      expect(wrapper.find('button[aria-label="Mark all as read"]').exists()).toBe(false)
    })

    it('loads the latest notifications whenever it opens', async () => {
      await render(makeUser(), { unread: 1, approvals: 0, invitations: 0 })
      backend.on('GET /api/notifications', [makeNotification()])
      await button('Notifications').trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('Bob invited you to "Standup"')
      expect(backend.calls('GET /api/notifications')).toHaveLength(1)
      expect(backend.calls('GET /api/notifications')[0]!.query.has('group')).toBe(false)
    })

    it('lists them by day, newest first, with how long ago each came', async () => {
      vi.useFakeTimers({ toFake: ['Date'] })
      vi.setSystemTime(new Date(2026, 0, 5, 9, 30))
      await render(makeUser(), { unread: 1, approvals: 0, invitations: 0 })
      backend.on('GET /api/notifications', [
        makeNotification(),
        makeNotification({
          id: 'n2',
          type: 'comment_added',
          created_at: '2026-01-04T18:00:00',
          read_at: '2026-01-04T19:00:00',
        }),
        makeNotification({
          id: 'n3',
          type: 'booking_approved',
          created_at: '2025-12-20T10:00:00',
          read_at: '2025-12-21T10:00:00',
        }),
      ])
      await button('Notifications').trigger('click')
      await flushPromises()
      vi.useRealTimers()

      const sections = wrapper.findAll('section').map((section) => ({
        day: section.get('h3').text(),
        items: section.findAll('li').map((li) => li.text()),
      }))
      expect(sections).toEqual([
        { day: 'Today', items: ['Bob invited you to "Standup"30 min. ago'] },
        { day: 'Yesterday', items: ['Bob commented on "Standup"yesterday'] },
        { day: 'Earlier', items: ['Bob approved "Standup"2025-12-20'] },
      ])
      expect(wrapper.text()).toContain('1 new')
      expect(wrapper.findAll('li button').map((b) => b.attributes('data-unread'))).toEqual([
        'true',
        undefined,
        undefined,
      ])
      expect(wrapper.get('time').attributes('title')).toBe('2026-01-05 09:00')
    })

    it('marks a notification read and shows its event when one is clicked', async () => {
      await render(makeUser(), { unread: 1, approvals: 0, invitations: 0 })
      backend.on('GET /api/notifications', [makeNotification()])
      backend.on('POST /api/notifications/n1/read', makeNotification({ read_at: '2026-01-05T10:00:00' }))
      await button('Notifications').trigger('click')
      await flushPromises()
      await wrapper.get('[data-unread]').trigger('click')
      await flushPromises()
      expect(backend.calls('POST /api/notifications/n1/read')).toHaveLength(1)
      expect(router.currentRoute.value.path).toBe('/event/e1')
      expect(wrapper.text()).not.toContain('Bob invited you')
    })

    it('shows where one already read leads without marking it again', async () => {
      await render()
      backend.on('GET /api/notifications', [makeNotification({ read_at: '2026-01-05T10:00:00' })])
      await button('Notifications').trigger('click')
      await flushPromises()
      await wrapper.get('li button').trigger('click')
      await flushPromises()
      expect(backend.calls('POST /api/notifications/n1/read')).toHaveLength(0)
      expect(router.currentRoute.value.path).toBe('/event/e1')
    })

    it('still shows where it leads if marking it read fails', async () => {
      await render(makeUser(), { unread: 1, approvals: 0, invitations: 0 })
      backend.on('GET /api/notifications', [makeNotification()])
      backend.on('POST /api/notifications/n1/read', reply(500))
      await button('Notifications').trigger('click')
      await flushPromises()
      await wrapper.find('li button').trigger('click')
      await flushPromises()
      expect(toasts.map((t) => t.tone)).toEqual(['error'])
      expect(router.currentRoute.value.path).toBe('/event/e1')
    })

    // The server says where each leads (the rule is tested there); the menu goes there.
    it.each([
      ['a calendar one was added to', { type: 'member_added', event_id: null, link: '/calendar/c1' }],
      ['an invitation to an event out of sight', { link: '/invitation/tok-1' }],
      ['an event cancelled since', { type: 'booking_cancelled', event_status: 'cancelled', link: '/notifications' }],
      ['an event deleted since', { event_id: null, link: '/notifications' }],
    ] as const)('leads to %s where the server says', async (_, overrides) => {
      await render()
      backend.on('GET /api/notifications', [makeNotification({ read_at: '2026-01-05T10:00:00', ...overrides })])
      await button('Notifications').trigger('click')
      await flushPromises()
      await wrapper.get('li button').trigger('click')
      await flushPromises()
      expect(router.currentRoute.value.path).toBe(overrides.link)
    })

    it('marks all notifications read', async () => {
      await render(makeUser(), { unread: 2, approvals: 0, invitations: 0 })
      backend.on('POST /api/notifications/read-all', { ok: true })
      await button('Notifications').trigger('click')
      await flushPromises()
      await button('Mark all as read').trigger('click')
      await flushPromises()
      expect(backend.calls('POST /api/notifications/read-all')).toHaveLength(1)
      expect(wrapper.find('button[aria-label="Mark all as read"]').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('new')
    })

    it('leads to the requests and invitations still waiting for an answer', async () => {
      await render(makeUser(), { unread: 0, approvals: 2, invitations: 1 })
      await button('Notifications').trigger('click')
      await flushPromises()
      expect(wrapper.findAll('[data-waiting]').map((b) => b.text())).toEqual([
        '2 requests await you',
        '1 invitation awaits your answer',
      ])
      await wrapper.get('[data-waiting="approvals"]').trigger('click')
      await flushPromises()
      expect(router.currentRoute.value.path).toBe('/notifications')
      expect(useNotificationsStore().group).toBe('approvals')
    })

    it('links to all notifications', async () => {
      await render()
      useNotificationsStore().group = 'approvals'
      await button('Notifications').trigger('click')
      await textButton('View all notifications').trigger('click')
      await flushPromises()
      expect(router.currentRoute.value.path).toBe('/notifications')
      expect(useNotificationsStore().group).toBeNull()
    })

    it('closes on a click outside and on Escape', async () => {
      await render()
      await button('Notifications').trigger('click')
      expect(wrapper.text()).toContain('View all notifications')
      document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
      await flushPromises()
      expect(wrapper.text()).not.toContain('View all notifications')

      await button('Notifications').trigger('click')
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      await flushPromises()
      expect(wrapper.text()).not.toContain('View all notifications')
    })
  })

  describe('menu', () => {
    it('leads to the account page', async () => {
      await render()
      await button('Menu').trigger('click')
      expect(wrapper.find('[role="menu"]').exists()).toBe(true)
      await textButton('Account settings').trigger('click')
      await flushPromises()
      expect(router.currentRoute.value.path).toBe('/account')
      expect(wrapper.find('[role="menu"]').exists()).toBe(false)
    })

    it('offers the administration only to administrators', async () => {
      await render()
      await button('Menu').trigger('click')
      expect(textButton('Administration')).toBeUndefined()
      wrapper.unmount()
      setActivePinia(createPinia())
      await render(makeUser({ is_admin: true }))
      await button('Menu').trigger('click')
      await textButton('Administration').trigger('click')
      await flushPromises()
      expect(router.currentRoute.value.path).toBe('/admin')
    })

    it('signs out and shows the login page', async () => {
      await render()
      backend.on('DELETE /api/auth/v1/auth/session', reply(401))
      await button('Menu').trigger('click')
      await textButton('Log out').trigger('click')
      await flushPromises()
      expect(backend.calls('DELETE /api/auth/v1/auth/session')).toHaveLength(1)
      expect(useAuthStore().isLoggedIn).toBe(false)
      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('closes on a click outside and on Escape', async () => {
      await render()
      await button('Menu').trigger('click')
      document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
      await flushPromises()
      expect(wrapper.find('[role="menu"]').exists()).toBe(false)
      await button('Menu').trigger('click')
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      await flushPromises()
      expect(wrapper.find('[role="menu"]').exists()).toBe(false)
    })
  })
})
