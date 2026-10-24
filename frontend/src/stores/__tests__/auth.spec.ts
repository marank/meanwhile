import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api'
import { realtime } from '@/services/realtime'
import { useAuthStore } from '../auth'

vi.mock('@/api', async (original) => ({
  ...(await original<typeof import('@/api')>()),
  login: vi.fn(),
  me: vi.fn(),
  updateProfile: vi.fn(),
}))

/** Delivers a message to the listeners of the shared realtime client, as the socket would. */
function receive(type: string) {
  const emit = (realtime as unknown as { emit(message: Record<string, unknown>): void }).emit.bind(realtime)
  emit({ type })
}

const user = { id: 'u1', timezone: null, language: null } as unknown as api.User

describe('auth store', () => {
  afterEach(() => {
    useAuthStore().$dispose()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  beforeEach(async () => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    vi.spyOn(realtime, 'start').mockImplementation(() => {})
    vi.spyOn(realtime, 'stop').mockImplementation(() => {})
    vi.mocked(api.login).mockResolvedValue(user)
    vi.mocked(api.updateProfile).mockResolvedValue(user)
    await useAuthStore().login('a@example.com', 'secret')
    await vi.runAllTimersAsync()
    vi.mocked(realtime.start).mockClear()
  })

  it('connects again when the live connection is refused but the session is still valid', async () => {
    vi.mocked(api.me).mockResolvedValue(user)
    receive('unauthenticated')
    await vi.runAllTimersAsync()
    expect(api.me).toHaveBeenCalled()
    expect(realtime.start).toHaveBeenCalledTimes(1)
  })

  it('waits a minute before connecting again if the socket keeps refusing', async () => {
    vi.mocked(api.me).mockResolvedValue(user)
    receive('unauthenticated')
    await vi.runAllTimersAsync()
    receive('unauthenticated')
    await vi.advanceTimersByTimeAsync(30_000)
    expect(realtime.start).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(30_000)
    expect(realtime.start).toHaveBeenCalledTimes(2)
  })

  it('leaves signing out to the unauthorized handler when the session is gone', async () => {
    vi.mocked(api.me).mockRejectedValue(new api.ApiError(401, null, 'Unauthorized'))
    receive('unauthenticated')
    await vi.runAllTimersAsync()
    expect(realtime.start).not.toHaveBeenCalled()
  })
})
