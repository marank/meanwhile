import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api'
import { realtime } from '@/services/realtime'
import { useCalendarStore } from '../calendars'

vi.mock('@/api', async (original) => ({
  ...(await original<typeof import('@/api')>()),
  getLayout: vi.fn(),
}))

/** Delivers a message to the listeners of the shared realtime client, as the socket would. */
function receive(type: string) {
  const emit = (realtime as unknown as { emit(message: { type: string }): void }).emit.bind(realtime)
  emit({ type })
}

const layout = (...calendars: api.CalendarListItem[]): api.Layout => ({ folders: [], calendars })
const calendar = (id: string) => ({ calendar: { id }, membership: {} }) as unknown as api.CalendarListItem

describe('calendar list live updates', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    vi.mocked(api.getLayout).mockResolvedValue(layout(calendar('a')))
  })

  afterEach(() => {
    useCalendarStore().$dispose()
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('loads the list again, once for a burst of changes', async () => {
    const store = useCalendarStore()
    await store.load()
    vi.mocked(api.getLayout).mockResolvedValue(layout(calendar('a'), calendar('b')))

    receive('calendars.changed')
    receive('calendars.changed')
    receive('reconnected')
    await vi.advanceTimersByTimeAsync(300)

    expect(api.getLayout).toHaveBeenCalledTimes(2)
    expect(store.items.map((i) => i.calendar.id)).toEqual(['a', 'b'])
  })

  it('does nothing before the first load, or after a reset', async () => {
    const store = useCalendarStore()
    receive('calendars.changed')
    await vi.advanceTimersByTimeAsync(300)
    expect(api.getLayout).not.toHaveBeenCalled()

    await store.load()
    receive('calendars.changed')
    store.reset()
    await vi.advanceTimersByTimeAsync(300)
    expect(api.getLayout).toHaveBeenCalledTimes(1)
  })

  it('stays quiet when the background load fails', async () => {
    const store = useCalendarStore()
    await store.load()
    vi.mocked(api.getLayout).mockRejectedValue(new Error('offline'))
    receive('calendars.changed')
    await vi.advanceTimersByTimeAsync(300)
    expect(store.items).toHaveLength(1)
  })
})
