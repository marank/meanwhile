import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter, type RouteMeta } from 'vue-router'
import { fakeBackend, reply } from '@/__tests__/fakeBackend'
import type { User } from '@/api'
import App from '@/App.vue'
import { i18n } from '@/i18n'
import { standaloneFramed } from '@/services/pageFrame'
import { toast, toasts } from '@/services/toast'
import { useAuthStore } from '@/stores/auth'
import { makeUser, sessionRoutes, stubBrowser } from '@/views/__tests__/session'

let wrapper: VueWrapper

const settings = { app_name: 'Team Calendar', logo_url: '', favicon_url: '' }

async function render(user: User | null, appSettings: object = settings, meta: RouteMeta = {}) {
  fakeBackend({
    ...sessionRoutes(user),
    'GET /api/settings': appSettings,
    'GET /api/notifications/counts': { unread: 0, approvals: 0, invitations: 0 },
  })
  await useAuthStore().init()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: defineComponent(() => () => h('p', 'The page')), meta }],
  })
  await router.push('/')
  wrapper = mount(App, {
    global: {
      plugins: [i18n, router],
      // The sidebar is tested on its own.
      stubs: { CalendarSidebar: defineComponent(() => () => h('aside', 'Sidebar')) },
    },
    attachTo: document.body,
  })
  await flushPromises()
}

beforeEach(() => {
  i18n.global.locale.value = 'en'
  setActivePinia(createPinia())
  stubBrowser()
  toasts.splice(0)
  document.head.querySelectorAll('link[rel="icon"]').forEach((link) => link.remove())
  document.title = ''
})

afterEach(() => {
  wrapper.unmount()
  vi.restoreAllMocks()
})

describe('App', () => {
  it('shows only the page while signed out', async () => {
    await render(null)
    expect(wrapper.text()).toContain('The page')
    expect(wrapper.find('header').exists()).toBe(false)
    expect(wrapper.find('aside').exists()).toBe(false)
  })

  it('adds the navbar and the sidebar while signed in', async () => {
    await render(makeUser())
    expect(wrapper.get('header').text()).toContain('Team Calendar')
    expect(wrapper.get('aside').text()).toBe('Sidebar')
    expect(wrapper.text()).toContain('The page')
  })

  it('leaves them out on pages of their own, unless the page asks for them', async () => {
    await render(makeUser(), settings, { standalone: true })
    expect(wrapper.find('header').exists()).toBe(false)
    expect(wrapper.find('aside').exists()).toBe(false)
    standaloneFramed.value = true
    await flushPromises()
    expect(wrapper.find('header').exists()).toBe(true)
    expect(wrapper.find('aside').exists()).toBe(true)
    standaloneFramed.value = false
  })

  it('shows toasts', async () => {
    await render(null)
    toast.success('Saved')
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toBe('Saved')
  })

  it('names the browser tab after the app', async () => {
    await render(null)
    expect(document.title).toBe('Team Calendar')
  })

  it('keeps the default name and icon when the settings cannot be loaded', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    await render(null, reply(500))
    expect(document.title).toBe('Meanwhile')
    expect(document.querySelector('link[rel="icon"]')).toBeNull()
  })

  it('uses the configured favicon', async () => {
    await render(null, { ...settings, favicon_url: '/media/favicon.png' })
    expect(document.querySelector<HTMLLinkElement>('link[rel="icon"]')!.getAttribute('href')).toBe('/media/favicon.png')
  })

  it('replaces the favicons the page came with', async () => {
    document.head.insertAdjacentHTML(
      'beforeend',
      '<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" href="/favicon.svg" type="image/svg+xml">',
    )
    await render(null, { ...settings, favicon_url: '/media/favicon.png' })
    const links = document.querySelectorAll('link[rel="icon"]')
    expect(links).toHaveLength(1)
    expect(links[0]!.getAttribute('href')).toBe('/media/favicon.png')
    expect(links[0]!.hasAttribute('type')).toBe(false)
  })
})
