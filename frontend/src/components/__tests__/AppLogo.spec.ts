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
  it('shows our logo when none was uploaded', async () => {
    await loadSettings({ app_name: 'team calendar' })
    expect(mount(AppLogo).get('img').attributes('src')).toBe('/logo.svg')
  })

  it('shows our logo before settings are loaded', () => {
    expect(mount(AppLogo).get('img').attributes('src')).toBe('/logo.svg')
  })

  it('shows the uploaded logo instead of ours', async () => {
    await loadSettings({ app_name: 'Team', logo_url: '/media/logo.png' })
    const wrapper = mount(AppLogo, { props: { size: 'lg' } })
    expect(wrapper.get('img').attributes('src')).toBe('/media/logo.png')
  })
})
