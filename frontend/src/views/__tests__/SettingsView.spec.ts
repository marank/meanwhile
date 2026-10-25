import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter, createWebHistory, RouterView } from 'vue-router'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import { buttonNamed, calendar, clearToasts, member, toastTexts } from '@/components/__tests__/settingsFixtures'
import SettingsView from '../SettingsView.vue'

let backend: FakeBackend

async function open(path = '/calendar/cal/settings', history = createMemoryHistory()) {
  const router = createRouter({
    history,
    routes: [
      { path: '/calendar/:calendarId/settings', component: SettingsView, props: true },
      { path: '/calendar/:id?', component: { render: () => h('p', 'calendar page') } },
    ],
  })
  await router.push(path)
  const App = defineComponent({ render: () => h(RouterView) })
  const wrapper = mount(App, { global: { plugins: [router, i18n] }, attachTo: document.body })
  await flushPromises()
  const tab = async (label: string) => {
    await wrapper
      .findAll('[role="tab"]')
      .find((t) => t.text() === label)!
      .trigger('click')
    await flushPromises()
  }
  return { wrapper, router, tab }
}

const title = (wrapper: Awaited<ReturnType<typeof open>>['wrapper']) => wrapper.get('h1').text()

describe('calendar settings page', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    clearToasts()
    backend = fakeBackend({
      'GET /api/calendars/cal': calendar(),
      'GET /api/calendars/other': calendar({ id: 'other', name: 'Other' }),
      'GET /api/calendars/*/members': [member('ann', 'Ann', 'owner')],
      'GET /api/calendars/*/groups': [],
      'GET /api/calendars/*/categories': [],
      'GET /api/calendars/*/resources': [],
      'GET /api/calendars/*/approvers': [],
      'GET /api/calendars/*/feed-url': { feed_url: 'https://cal.test/feed.ics' },
      'GET /api/search': [],
    })
  })

  it('shows the calendar and opens on the general tab', async () => {
    const { wrapper } = await open()
    expect(title(wrapper)).toBe('Settings: Team')
    expect(wrapper.findAll('[role="tab"]').map((t) => t.text())).toEqual([
      'General',
      'Access',
      'Categories',
      'Resources',
      'Share',
    ])
    expect(wrapper.text()).toContain('Only allow all-day events')
    // The owner may change it.
    expect(buttonNamed(wrapper, 'Save').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('switches tabs in the URL, loading each tab once', async () => {
    const { wrapper, router, tab } = await open()
    await tab('Access')
    expect(router.currentRoute.value.query.tab).toBe('access')
    expect(wrapper.text()).toContain('Can view events.')
    await tab('Categories')
    expect(wrapper.text()).toContain('No categories yet.')
    await tab('Resources')
    expect(wrapper.text()).toContain('No resources yet.')
    await tab('Share')
    expect(wrapper.text()).toContain('https://cal.test/feed.ics')
    await tab('Access')
    expect(backend.calls('GET /api/calendars/cal/members')).toHaveLength(1)
    expect(backend.calls('GET /api/calendars/cal')).toHaveLength(1)
    wrapper.unmount()
  })

  it('opens the tab named in the URL, and the first one for an unknown name', async () => {
    const { wrapper, router } = await open('/calendar/cal/settings?tab=share')
    expect(wrapper.text()).toContain('https://cal.test/feed.ics')
    await router.replace({ query: { tab: 'nonsense' } })
    await flushPromises()
    expect(router.currentRoute.value.query.tab).toBe('general')
    wrapper.unmount()
  })

  it('shows the saved calendar after a change in a tab', async () => {
    backend.on('PATCH /api/calendars/cal', (req) =>
      calendar({ ...(req.body as Partial<api.Calendar>), name: 'Renamed' }),
    )
    const { wrapper } = await open()
    await wrapper.findAll('[role="switch"]').at(-1)!.trigger('click')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(title(wrapper)).toBe('Settings: Renamed')
    wrapper.unmount()
  })

  it('lets members without the manage role only look', async () => {
    backend.on('GET /api/calendars/cal', calendar({ my_membership: member('ann', 'Ann', 'full') }))
    const { wrapper } = await open()
    expect(buttonNamed(wrapper, 'Save').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('reports a calendar that cannot be loaded, and keeps showing that it loads', async () => {
    backend.on('GET /api/calendars/cal', reply(404, { detail: 'Not found.' }))
    const { wrapper } = await open()
    expect(toastTexts()).toEqual(['Not found.'])
    expect(title(wrapper)).toBe('Settings:')
    expect(wrapper.get('[role="status"]').text()).toBe('Loading…')
    wrapper.unmount()
  })

  it('loads another calendar afresh, ignoring a late answer for the one before', async () => {
    let answerFirst!: () => void
    backend.on(
      'GET /api/calendars/cal',
      () => new Promise((resolve) => (answerFirst = () => resolve(calendar({ name: 'Late' })))),
    )
    const { wrapper, router } = await open()
    await router.push('/calendar/other/settings')
    await flushPromises()
    expect(title(wrapper)).toBe('Settings: Other')
    answerFirst()
    await flushPromises()
    expect(title(wrapper)).toBe('Settings: Other')
    wrapper.unmount()
  })

  it('ignores a late failure for a calendar no longer shown', async () => {
    let failFirst!: () => void
    backend.on('GET /api/calendars/cal', () => new Promise((resolve) => (failFirst = () => resolve(reply(500)))))
    const { wrapper, router } = await open()
    await router.push('/calendar/other/settings')
    await flushPromises()
    failFirst()
    await flushPromises()
    expect(toastTexts()).toEqual([])
    wrapper.unmount()
  })

  it('goes back to the calendar when opened directly', async () => {
    const { wrapper, router } = await open()
    await buttonNamed(wrapper, 'Back').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/calendar/cal')
    expect(wrapper.text()).toBe('calendar page')
    wrapper.unmount()
  })

  it('goes back to where it was opened from', async () => {
    // Only the browser's history knows the page before.
    const { wrapper, router } = await open('/calendar', createWebHistory())
    await router.push('/calendar/cal/settings')
    await flushPromises()
    await buttonNamed(wrapper, 'Back').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/calendar'))
    wrapper.unmount()
  })
})
