import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import * as api from '@/api'
import { i18n } from '@/i18n'
import AccountView from '../AccountView.vue'

vi.mock('@/api', async (original) => ({
  ...(await original<typeof import('@/api')>()),
  listAppPasswords: vi.fn(),
}))

// The other two tabs aren't of interest here; their stores and requests stay out of it.
const stubs = {
  AccountGeneralSettings: { template: '<p>general</p>' },
  OverviewSettingsPanel: { template: '<p>overview</p>' },
}

async function open() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/account', component: AccountView }],
  })
  await router.push('/account')
  const wrapper = mount(AccountView, { global: { plugins: [router, i18n], stubs } })
  await flushPromises()
  const select = async (tab: string) => {
    await router.replace({ query: { tab } })
    await flushPromises()
  }
  return { wrapper, select }
}

describe('settings tabs', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    vi.mocked(api.listAppPasswords).mockResolvedValue([{ id: '1', label: 'Phone', created_at: '', last_used_at: null }])
  })

  afterEach(() => vi.clearAllMocks())

  it('loads a tab when it is first opened, and not again when coming back to it', async () => {
    const { wrapper, select } = await open()
    expect(api.listAppPasswords).not.toHaveBeenCalled()

    await select('appPasswords')
    expect(api.listAppPasswords).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Phone')

    await select('general')
    await select('appPasswords')
    await select('overview')
    await select('appPasswords')
    expect(api.listAppPasswords).toHaveBeenCalledTimes(1)
    // The data is still there, without waiting for a request.
    expect(wrapper.text()).toContain('Phone')
    wrapper.unmount()
  })

  it('loads afresh when the page is opened anew', async () => {
    const first = await open()
    await first.select('appPasswords')
    first.wrapper.unmount()

    const second = await open()
    await second.select('appPasswords')
    expect(api.listAppPasswords).toHaveBeenCalledTimes(2)
    second.wrapper.unmount()
  })
})
