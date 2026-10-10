import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api'
import { useCalendarStore } from '../calendars'
import { useEventStore } from '../events'
import { deferred } from './deferred'

vi.mock('@/api', async (original) => ({
  ...(await original<typeof import('@/api')>()),
  listEvents: vi.fn(),
}))

const occurrence = (title: string) => ({ title }) as api.Occurrence

describe('event store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.listEvents).mockReset()
    useCalendarStore().items = [{ calendar: { id: 'c1' }, membership: { folder_id: null } } as api.CalendarListItem]
  })

  it('ignores a slow answer for a range that is no longer shown', async () => {
    const events = useEventStore()
    const january = deferred<api.Occurrence[]>()
    const february = deferred<api.Occurrence[]>()
    vi.mocked(api.listEvents).mockReturnValueOnce(january.promise).mockReturnValueOnce(february.promise)

    const first = events.load(new Date(2026, 0, 1), new Date(2026, 1, 1))
    const second = events.load(new Date(2026, 1, 1), new Date(2026, 2, 1))
    february.resolve([occurrence('February')])
    await second
    january.resolve([occurrence('January')])
    await first

    expect(events.occurrences.map((o) => o.title)).toEqual(['February'])
  })

  it('skips reloading the range already shown unless forced', async () => {
    const events = useEventStore()
    vi.mocked(api.listEvents).mockResolvedValue([])
    const start = new Date(2026, 0, 1)
    const end = new Date(2026, 1, 1)
    await events.load(start, end)
    await events.load(start, end)
    expect(api.listEvents).toHaveBeenCalledTimes(1)
    await events.load(start, end, true)
    expect(api.listEvents).toHaveBeenCalledTimes(2)
  })

  it('asks for all selected calendars in one request', async () => {
    useCalendarStore().items.push({ calendar: { id: 'c2' }, membership: { folder_id: null } } as api.CalendarListItem)
    vi.mocked(api.listEvents).mockResolvedValue([])
    await useEventStore().load(new Date(2026, 0, 1), new Date(2026, 1, 1))
    expect(api.listEvents).toHaveBeenCalledOnce()
    expect(vi.mocked(api.listEvents).mock.calls[0]![0]).toEqual(['c1', 'c2'])
  })
})
