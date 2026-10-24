import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { fakeBackend } from '@/__tests__/fakeBackend'
import { useSettingsStore } from '@/stores/settings'
import AppLogo from '../AppLogo.vue'

async function loadSettings(settings: Record<string, unknown>) {
  fakeBackend({ 'GET /api/settings': { app_name: '', logo_url: null, favicon_url: null, ...settings } })
  await useSettingsStore().load()
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('AppLogo', () => {
  it("shows the app name's initial when there is no logo", async () => {
    await loadSettings({ app_name: 'team calendar' })
    const wrapper = mount(AppLogo)
    expect(wrapper.text()).toBe('T')
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('falls back to the default name before settings are loaded', () => {
    expect(mount(AppLogo).text()).toBe('M')
  })

  it('shows the uploaded logo instead of the initial', async () => {
    await loadSettings({ app_name: 'Team', logo_url: '/media/logo.png' })
    const wrapper = mount(AppLogo, { props: { size: 'lg' } })
    expect(wrapper.get('img').attributes('src')).toBe('/media/logo.png')
    expect(wrapper.text()).toBe('')
  })
})
