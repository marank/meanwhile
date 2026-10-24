import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { fakeBackend, reply, type FakeBackend } from '@/__tests__/fakeBackend'
import type * as api from '@/api'
import { useCalendarStore } from '../calendars'

function calendarItem(id: string, role = 'owner', folder_id: string | null = null, position = 0) {
  return {
    calendar: { id, name: id, url_path: null } as unknown as api.Calendar,
    membership: { folder_id, position, role } as api.CalendarMember,
    access: 'member',
  } as api.CalendarListItem
}

describe('calendar store changes', () => {
  let backend: FakeBackend
  let layout: api.Layout

  beforeEach(async () => {
    setActivePinia(createPinia())
    layout = {
      folders: [{ id: 'f', name: 'Folder', parent_id: null, position: 0 }],
      calendars: [calendarItem('a'), calendarItem('b', 'read')],
    }
    backend = fakeBackend({ 'GET /api/layout': () => layout })
    await useCalendarStore().load()
    backend.requests.length = 0
  })

  afterEach(() => useCalendarStore().$dispose())

  it('creates only where the selected calendar lets one add own events', () => {
    const store = useCalendarStore()
    store.select('a')
    expect(store.canCreateInSelected).toBe(true)
    store.select('b')
    expect(store.canCreateInSelected).toBe(false)
    store.select('f')
    expect(store.canCreateInSelected).toBe(false)
    expect(store.selectedFolder?.name).toBe('Folder')
    store.select('missing')
    expect(store.selectedCalendarIds).toEqual([])
  })

  it('lists folders and calendars of a folder together', () => {
    const store = useCalendarStore()
    expect(store.childrenOf(null).map((c) => c.id)).toEqual(['f', 'a', 'b'])
    expect(store.childrenOf('f')).toEqual([])
  })

  it('creates and deletes calendars, then shows the new list', async () => {
    const store = useCalendarStore()
    backend.on('POST /api/calendars', { id: 'c', name: 'New' })
    backend.on('DELETE /api/calendars/*', undefined)
    layout.calendars.push(calendarItem('c'))
    await expect(store.createCalendar('New')).resolves.toMatchObject({ id: 'c' })
    expect(store.items.map((i) => i.calendar.id)).toContain('c')

    layout.calendars.pop()
    await store.deleteCalendar('c')
    expect(store.items.map((i) => i.calendar.id)).not.toContain('c')
    expect(backend.unhandled).toEqual([])
  })

  it('updates a calendar in place', async () => {
    const store = useCalendarStore()
    backend.on('PATCH /api/calendars/a', { id: 'a', name: 'Renamed' })
    await store.updateCalendar('a', { name: 'Renamed' })
    expect(store.calendarsById.get('a')?.name).toBe('Renamed')
    backend.on('PATCH /api/calendars/z', { id: 'z', name: 'Other' })
    await store.updateCalendar('z', { name: 'Other' })
    expect(store.calendarsById.has('z')).toBe(false)
  })

  it('creates, renames and deletes folders, loading again each time', async () => {
    const store = useCalendarStore()
    backend.on('POST /api/layout/folders', { id: 'g' })
    backend.on('PATCH /api/layout/folders/*', { id: 'g' })
    backend.on('DELETE /api/layout/folders/*', undefined)
    await store.createFolder('Sub', 'f')
    await store.renameFolder('g', 'Renamed')
    await store.deleteFolder('g')
    expect(backend.calls('GET /api/layout')).toHaveLength(3)
    expect(backend.calls('POST /api/layout/folders')[0]!.body).toEqual({ name: 'Sub', parent_id: 'f' })
  })

  it('moves calendars and folders at once and saves the move', async () => {
    const store = useCalendarStore()
    backend.on('PATCH /api/layout/items', undefined)
    await store.reorder([
      { type: 'calendar', id: 'b', parent_id: 'f', position: 0 },
      { type: 'calendar', id: 'a', parent_id: 'f', position: 1 },
      { type: 'folder', id: 'f', parent_id: null, position: 5 },
      { type: 'folder', id: 'gone', parent_id: null, position: 0 },
      { type: 'calendar', id: 'gone', parent_id: null, position: 0 },
    ])
    expect(store.calendarsIn('f').map((i) => i.calendar.id)).toEqual(['b', 'a'])
    expect(backend.calls('GET /api/layout')).toHaveLength(0)
  })

  it('puts things back where the server has them when it refuses a move', async () => {
    const store = useCalendarStore()
    backend.on('PATCH /api/layout/items', reply(403))
    await expect(store.reorder([{ type: 'calendar', id: 'a', parent_id: 'f', position: 0 }])).rejects.toMatchObject({
      status: 403,
    })
    expect(store.calendarsIn('f')).toEqual([])
  })
})
