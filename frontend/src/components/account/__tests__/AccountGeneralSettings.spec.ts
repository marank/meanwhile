import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { realtime } from '@/services/realtime'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import { buttonNamed, clearToasts, toastTexts, user } from '@/components/__tests__/settingsFixtures'
import AccountGeneralSettings from '../AccountGeneralSettings.vue'

let backend: FakeBackend

function render() {
  return mount(AccountGeneralSettings, { global: { plugins: [i18n] }, attachTo: document.body })
}

/** Opens the select at `index` and picks the option with `text`. */
async function choose(wrapper: ReturnType<typeof render>, index: number, text: string) {
  await wrapper.findAll('[role="combobox"]')[index]!.trigger('click')
  ;[...document.querySelectorAll<HTMLElement>('[role="option"]')].find((o) => o.textContent!.trim() === text)!.click()
  await flushPromises()
}

describe('account general settings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    clearToasts()
    localStorage.clear()
    // jsdom has no media queries; the color scheme store asks for one.
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: () => {} }))
    vi.spyOn(realtime, 'start').mockImplementation(() => {})
    vi.spyOn(realtime, 'stop').mockImplementation(() => {})
    let saved = user({ time_format: '24h' })
    useAuthStore().user = saved
    backend = fakeBackend({
      'PATCH /api/users/me': (req) => (saved = { ...saved, ...(req.body as Partial<api.User>) }),
      'POST /api/auth/v1/account/password/change': { status: 200 },
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    i18n.global.locale.value = 'en'
  })

  it('starts with the account as it is', () => {
    const wrapper = render()
    expect((wrapper.get('input:not([type])').element as HTMLInputElement).value).toBe('Ann')
    expect(wrapper.findAll('[role="combobox"]').map((c) => c.text())).toEqual([
      'English',
      'System',
      '24-hour',
      'Automatic (browser locale)',
    ])
    wrapper.unmount()
  })

  it('saves name, language, formats and color scheme, and confirms in the new language', async () => {
    const wrapper = render()
    await wrapper.get('input:not([type])').setValue('Annie')
    await choose(wrapper, 1, 'Dark')
    await choose(wrapper, 2, '12-hour')
    await choose(wrapper, 3, '2026-12-31')
    await choose(wrapper, 0, 'Deutsch')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(backend.calls('PATCH /api/users/me')[0]!.body).toEqual({
      display_name: 'Annie',
      time_format: '12h',
      date_format: 'ymd',
      language: 'de',
    })
    expect(useAuthStore().user!.display_name).toBe('Annie')
    expect(i18n.global.locale.value).toBe('de')
    expect(useThemeStore().preference).toBe('dark')
    expect(toastTexts()).toEqual([i18n.global.t('app.settingsSaved')])
    expect(toastTexts()[0]).not.toBe('Settings saved.')
    wrapper.unmount()
  })

  it('reports a failed save and keeps the language', async () => {
    backend.on('PATCH /api/users/me', reply(500))
    const wrapper = render()
    await choose(wrapper, 0, 'Deutsch')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(toastTexts()).toEqual(['Could not save the changes.'])
    expect(i18n.global.locale.value).toBe('en')
    wrapper.unmount()
  })

  it('changes the password by its own button and empties the fields', async () => {
    const wrapper = render()
    const [current, next] = wrapper.findAll('input[type="password"]')
    await current!.setValue('old-secret')
    await next!.setValue('new-secret-1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(backend.calls('POST /api/auth/v1/account/password/change')[0]!.body).toEqual({
      current_password: 'old-secret',
      new_password: 'new-secret-1',
    })
    expect(backend.calls('PATCH /api/users/me')).toHaveLength(0)
    expect(toastTexts()).toEqual(['Password changed.'])
    expect((current!.element as HTMLInputElement).value).toBe('')
    expect((next!.element as HTMLInputElement).value).toBe('')
    wrapper.unmount()
  })

  it('keeps the passwords when the change fails', async () => {
    backend.on('POST /api/auth/v1/account/password/change', reply(400))
    const wrapper = render()
    const [current] = wrapper.findAll('input[type="password"]')
    await current!.setValue('wrong')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(toastTexts()).toEqual(['Could not change the password.'])
    expect((current!.element as HTMLInputElement).value).toBe('wrong')
    wrapper.unmount()
  })
})
