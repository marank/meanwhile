import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { realtime } from '@/services/realtime'
import { useAuthStore } from '@/stores/auth'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import {
  answerConfirm,
  appColors,
  buttonNamed,
  clearToasts,
  toastTexts,
  user,
} from '@/components/__tests__/settingsFixtures'
import AppPasswordsPanel from '../AppPasswordsPanel.vue'
import EmailNotificationsPanel from '../EmailNotificationsPanel.vue'
import OverviewSettingsPanel from '../OverviewSettingsPanel.vue'

let backend: FakeBackend

beforeEach(() => {
  setActivePinia(createPinia())
  i18n.global.locale.value = 'en'
  clearToasts()
})

describe('app passwords', () => {
  const appPassword = (id: string, label: string, lastUsed: string | null = null): api.AppPassword => ({
    id,
    label,
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: lastUsed,
  })

  async function render() {
    const wrapper = mount(AppPasswordsPanel, { global: { plugins: [i18n] } })
    await flushPromises()
    return wrapper
  }

  beforeEach(() => {
    backend = fakeBackend({
      'GET /api/users/me/app-passwords': [
        appPassword('p1', 'Phone', '2026-03-04T10:00:00Z'),
        appPassword('p2', 'Laptop'),
      ],
    })
  })

  it('lists the app passwords and when they were last used', async () => {
    const wrapper = await render()
    const rows = wrapper.findAll('tbody tr').map((r) => r.text())
    expect(rows[0]).toContain('Phone')
    expect(rows[0]).toContain('2026')
    expect(rows[1]).toContain('Laptop')
    expect(rows[1]).toContain('Never')
  })

  it('says so when there are none', async () => {
    backend.on('GET /api/users/me/app-passwords', [])
    const wrapper = await render()
    expect(wrapper.text()).toContain('No app passwords yet.')
  })

  it('creates one and shows its secret once', async () => {
    backend.on('POST /api/users/me/app-passwords', { ...appPassword('p3', 'Tablet'), password: 'abcd-efgh' })
    const wrapper = await render()
    expect(buttonNamed(wrapper, 'Add').attributes('disabled')).toBeDefined()
    await wrapper.get('input').setValue('Tablet')
    await buttonNamed(wrapper, 'Add').trigger('click')
    await flushPromises()
    expect(backend.calls('POST /api/users/me/app-passwords')[0]!.body).toEqual({ label: 'Tablet' })
    expect(wrapper.text()).toContain('abcd-efgh')
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('')
    expect(backend.calls('GET /api/users/me/app-passwords')).toHaveLength(2)
    expect(toastTexts()).toEqual(['App password created.'])
  })

  it('reports a failed creation', async () => {
    backend.on('POST /api/users/me/app-passwords', reply(500))
    const wrapper = await render()
    await wrapper.get('input').setValue('Tablet')
    await buttonNamed(wrapper, 'Add').trigger('click')
    await flushPromises()
    expect(toastTexts()).toEqual(['Could not save the changes.'])
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('Tablet')
  })

  it('revokes one once confirmed', async () => {
    backend.on('DELETE /api/users/me/app-passwords/*', undefined)
    const wrapper = await render()
    await wrapper.findAll('button[aria-label="Delete"]')[1]!.trigger('click')
    await answerConfirm(false)
    expect(backend.calls('DELETE /api/users/me/app-passwords/*')).toHaveLength(0)
    await wrapper.findAll('button[aria-label="Delete"]')[1]!.trigger('click')
    await answerConfirm(true)
    expect(backend.calls('DELETE /api/users/me/app-passwords/p2')).toHaveLength(1)
    expect(toastTexts()).toEqual(['App password revoked.'])
  })
})

describe('email notifications', () => {
  beforeEach(() => {
    vi.spyOn(realtime, 'start').mockImplementation(() => {})
    vi.spyOn(realtime, 'stop').mockImplementation(() => {})
    const saved = user()
    useAuthStore().user = saved
    backend = fakeBackend({ 'PATCH /api/users/me': (req) => ({ ...saved, ...(req.body as Partial<api.User>) }) })
  })

  afterEach(() => vi.restoreAllMocks())

  it('shows one switch per kind, with the address they go to', () => {
    const wrapper = mount(EmailNotificationsPanel, { global: { plugins: [i18n] } })
    expect(wrapper.text()).toContain('ann@example.test')
    const switches = wrapper.findAll('[role="switch"]')
    expect(switches).toHaveLength(7)
    expect(switches.every((s) => s.attributes('aria-checked') === 'true')).toBe(true)
  })

  it('saves the chosen kinds', async () => {
    const wrapper = mount(EmailNotificationsPanel, { global: { plugins: [i18n] } })
    const comments = wrapper.findAll('[role="switch"]').find((s) => s.text().startsWith('Comments'))!
    await comments.trigger('click')
    expect(comments.attributes('aria-checked')).toBe('false')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/users/me')[0]!.body).toEqual({
      email_notifications: { ...user().email_notifications, comments: false },
    })
    expect(useAuthStore().user!.email_notifications.comments).toBe(false)
    expect(toastTexts()).toEqual(['Settings saved.'])
  })

  it('reports a failed save', async () => {
    backend.on('PATCH /api/users/me', reply(500))
    const wrapper = mount(EmailNotificationsPanel, { global: { plugins: [i18n] } })
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(toastTexts()).toEqual(['Could not save the changes.'])
  })
})

describe('overview settings', () => {
  const settings: api.OverviewSettings = {
    first_weekday: 1,
    show_weekends: true,
    weekend_days: [0, 6],
    show_week_numbers: false,
    use_calendar_colors: false,
    ...appColors,
  }

  async function render() {
    const wrapper = mount(OverviewSettingsPanel, { global: { plugins: [i18n] }, attachTo: document.body })
    await flushPromises()
    return wrapper
  }

  beforeEach(() => {
    backend = fakeBackend({
      'GET /api/users/me/settings': settings,
      'PATCH /api/users/me/settings': (req) => ({ ...settings, ...(req.body as object) }),
    })
  })

  it('saves only what changed', async () => {
    const wrapper = await render()
    const switches = wrapper.findAll('[role="switch"]')
    await switches.find((s) => s.text().startsWith('Events in their calendar color'))!.trigger('click')
    await switches.find((s) => s.text().startsWith('Show week numbers'))!.trigger('click')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/users/me/settings')[0]!.body).toEqual({
      use_calendar_colors: true,
      show_week_numbers: true,
    })
    expect(toastTexts()).toEqual(['Overview settings saved.'])
    wrapper.unmount()
  })

  it('sends nothing when nothing changed', async () => {
    const wrapper = await render()
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/users/me/settings')).toHaveLength(0)
    expect(toastTexts()).toEqual(['Overview settings saved.'])
    wrapper.unmount()
  })

  it('cannot save before the settings are loaded', async () => {
    backend.on('GET /api/users/me/settings', reply(500))
    const wrapper = await render()
    expect(toastTexts()).toEqual(['Could not load the requested settings.'])
    expect(buttonNamed(wrapper, 'Save').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('reports a failed save', async () => {
    backend.on('PATCH /api/users/me/settings', reply(500))
    const wrapper = await render()
    await wrapper.findAll('[role="switch"]')[0]!.trigger('click')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(toastTexts()).toEqual(['Could not save the changes.'])
    wrapper.unmount()
  })
})
