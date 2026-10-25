import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import { useOverviewStore } from '../overview'
import { useSettingsStore } from '../settings'

describe('app settings store', () => {
  let backend: FakeBackend

  beforeEach(() => {
    setActivePinia(createPinia())
    backend = fakeBackend({
      'GET /api/settings': { app_name: 'Team Cal', logo_url: '/logo.png', favicon_url: '' },
      'PATCH /api/admin/settings': (r) => ({
        app_name: '',
        logo_url: '',
        favicon_url: '/f.ico',
        ...(r.body as object),
      }),
    })
  })

  it('names the app Meanwhile until settings say otherwise', async () => {
    const store = useSettingsStore()
    expect(store.appName).toBe('Meanwhile')
    expect(store.logoUrl).toBeNull()
    await store.load()
    expect(store.appName).toBe('Team Cal')
    expect(store.logoUrl).toBe('/logo.png')
  })

  it('keeps the defaults when the settings cannot be loaded', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    backend.on('GET /api/settings', reply(500))
    const store = useSettingsStore()
    await store.load()
    expect(store.appName).toBe('Meanwhile')
    expect(log).toHaveBeenCalled()
    log.mockRestore()
  })

  it('saves new settings', async () => {
    const store = useSettingsStore()
    await expect(store.update({ app_name: '' } as never)).resolves.toMatchObject({ favicon_url: '/f.ico' })
    expect(store.appName).toBe('Meanwhile')
    expect(store.faviconUrl).toBe('/f.ico')
  })
})

describe('overview settings store', () => {
  let backend: FakeBackend

  beforeEach(() => {
    setActivePinia(createPinia())
    backend = fakeBackend({
      'GET /api/users/me/settings': { week_start: 1 },
      'PATCH /api/users/me/settings': (r) => ({ week_start: 1, ...(r.body as object) }),
    })
  })

  afterEach(() => useOverviewStore().reset())

  it('loads once, however often asked', async () => {
    const store = useOverviewStore()
    await Promise.all([store.load(), store.load()])
    await store.load()
    expect(backend.calls('GET /api/users/me/settings')).toHaveLength(1)
    expect(store.settings).toEqual({ week_start: 1 })
  })

  it('tries again after a failed load', async () => {
    backend.on('GET /api/users/me/settings', reply(500))
    const store = useOverviewStore()
    await expect(store.load()).rejects.toMatchObject({ status: 500 })
    backend.on('GET /api/users/me/settings', { week_start: 0 })
    await store.load()
    expect(store.settings).toEqual({ week_start: 0 })
  })

  it('saves changes and loads afresh after a reset', async () => {
    const store = useOverviewStore()
    await store.update({ week_start: 3 } as never)
    expect(store.settings).toEqual({ week_start: 3 })
    store.reset()
    expect(store.settings).toBeNull()
    await store.load()
    expect(backend.calls('GET /api/users/me/settings')).toHaveLength(1)
  })
})
