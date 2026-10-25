import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { i18n } from '@/i18n'
import { fakeBackend, type FakeBackend } from '@/__tests__/fakeBackend'
import { buttonNamed, clearToasts } from '@/components/__tests__/settingsFixtures'
import AdminView from '../AdminView.vue'

let backend: FakeBackend

async function open(path = '/admin') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin', component: AdminView },
      { path: '/calendar', component: { render: () => h('p', 'calendar page') } },
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

describe('administration page', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    clearToasts()
    backend = fakeBackend({
      'GET /api/admin/settings': {
        id: 1,
        app_name: 'Meanwhile',
        logo_url: '',
        favicon_url: '',
        default_first_weekday: 1,
        default_show_weekends: true,
        default_weekend_days: [0, 6],
        default_show_week_numbers: false,
      },
      'GET /api/admin/users': [],
      'GET /api/groups': [],
    })
  })

  it('opens on the general settings and switches between the tabs, loading each once', async () => {
    const { wrapper, router, tab } = await open()
    expect(wrapper.get('h1').text()).toBe('Administration')
    expect(wrapper.findAll('[role="tab"]').map((t) => t.text())).toEqual(['General', 'Users', 'Groups'])
    expect(wrapper.findAll('[role="tab"]').every((t) => t.find('svg[aria-hidden="true"]').exists())).toBe(true)
    expect(wrapper.text()).toContain('App name')

    await tab('Users')
    expect(router.currentRoute.value.query.tab).toBe('users')
    expect(wrapper.text()).toContain('No users yet.')
    await tab('Groups')
    expect(wrapper.text()).toContain('No groups yet.')
    await tab('Users')
    await tab('General')
    expect(backend.calls('GET /api/admin/users')).toHaveLength(1)
    expect(backend.calls('GET /api/admin/settings')).toHaveLength(1)
    wrapper.unmount()
  })

  it('opens the tab named in the URL', async () => {
    const { wrapper } = await open('/admin?tab=groups')
    expect(wrapper.text()).toContain('No groups yet.')
    expect(backend.calls('GET /api/admin/settings')).toHaveLength(0)
    wrapper.unmount()
  })

  it('goes back to the calendar when opened directly', async () => {
    const { wrapper, router } = await open()
    await buttonNamed(wrapper, 'Back').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/calendar')
    wrapper.unmount()
  })
})
