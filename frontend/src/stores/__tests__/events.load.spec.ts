import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import type * as api from '@/api'
import { i18n } from '@/i18n'
import { realtime } from '@/services/realtime'
import { toasts } from '@/services/toast'
import { useCalendarStore } from '../calendars'
import { useEventStore } from '../events'

function receive(message: Record<string, unknown>) {
  const emit = (realtime as unknown as { emit(message: Record<string, unknown>): void }).emit.bind(realtime)
  emit(message)
}

const calendarItem = (id: string) =>
  ({ calendar: { id, name: id }, membership: { folder_id: null, position: 0, role: 'owner' } }) as api.CalendarListItem

const occurrence = (event_id: string, calendar_id: string) => ({ event_id, calendar_id }) as api.Occurrence

const start = new Date('2026-01-01T00:00:00Z')
const end = new Date('2026-01-08T00:00:00Z')

describe('event store loading', () => {
  let backend: FakeBackend

  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
    toasts.splice(0)
    vi.spyOn(realtime, 'setCalendars').mockImplementation(() => {})
    backend = fakeBackend({
      'GET /api/events': (r) => r.query.getAll('calendar_ids').map((id) => occurrence(`${id}-1`, id)),
    })
    useCalendarStore().items = [calendarItem('a'), calendarItem('b')]
  })

  afterEach(() => {
    useEventStore().reset()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('follows the selected calendars live', async () => {
    useEventStore()
    expect(realtime.setCalendars).toHaveBeenLastCalledWith(['a', 'b'])
    useCalendarStore().select('a')
    await vi.waitFor(() => expect(realtime.setCalendars).toHaveBeenLastCalledWith(['a']))
  })

  it('drops the events of calendars no longer selected at once', async () => {
    const events = useEventStore()
    await events.load(start, end)
    expect(events.occurrences).toHaveLength(2)
    useCalendarStore().select('a')
    backend.on('GET /api/events', () => new Promise(() => {}))
    void events.load(start, end)
    expect(events.occurrences.map((o) => o.event_id)).toEqual(['a-1'])
  })

  it('asks nothing when no calendar is selected', async () => {
    const events = useEventStore()
    useCalendarStore().select('none')
    await events.load(start, end)
    expect(events.occurrences).toEqual([])
    expect(backend.requests).toHaveLength(0)
  })

  it('shows an error and allows trying the same range again', async () => {
    backend.on('GET /api/events', reply(500, { detail: 'Database down' }))
    const events = useEventStore()
    await events.load(start, end)
    expect(toasts.map((t) => t.tone)).toEqual(['error'])
    backend.on('GET /api/events', [])
    await events.load(start, end)
    expect(backend.calls('GET /api/events')).toHaveLength(2)
  })

  it('loads the range shown again when its events change elsewhere, once per burst', async () => {
    vi.useFakeTimers()
    const events = useEventStore()
    await events.load(start, end)
    receive({ type: 'events.changed', calendar_id: 'a' })
    receive({ type: 'events.changed', calendar_id: 'b' })
    receive({ type: 'events.changed', calendar_id: 'other' })
    await vi.advanceTimersByTimeAsync(300)
    expect(backend.calls('GET /api/events')).toHaveLength(2)
  })

  it('does not load after a reset', async () => {
    vi.useFakeTimers()
    const events = useEventStore()
    await events.load(start, end)
    events.reset()
    receive({ type: 'reconnected' })
    await vi.advanceTimersByTimeAsync(300)
    expect(backend.calls('GET /api/events')).toHaveLength(1)
    expect(events.occurrences).toEqual([])
  })
})
