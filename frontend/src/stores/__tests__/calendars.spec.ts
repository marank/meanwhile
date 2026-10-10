import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api'
import { ALL_CALENDARS, useCalendarStore } from '../calendars'
import { deferred } from './deferred'

vi.mock('@/api', async (original) => ({
  ...(await original<typeof import('@/api')>()),
  listCalendars: vi.fn(),
  listFolders: vi.fn(),
}))

function folder(id: string, parent_id: string | null = null): api.Folder {
  return { id, name: id, parent_id, position: 0 }
}

function calendarItem(id: string, folder_id: string | null = null): api.CalendarListItem {
  return {
    calendar: { id, name: id } as api.Calendar,
    membership: { folder_id, position: 0, role: 'owner' } as api.CalendarMember,
  }
}

describe('calendar store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('builds the folder tree', () => {
    const store = useCalendarStore()
    store.folders = [folder('a'), folder('b', 'a'), folder('c', 'b')]
    store.items = [calendarItem('x'), calendarItem('y', 'a'), calendarItem('z', 'c')]
    expect(store.childFolders(null).map((f) => f.id)).toEqual(['a'])
    expect(store.calendarsIn(null).map((i) => i.calendar.id)).toEqual(['x'])
    expect(store.descendantFolderIds('a').sort()).toEqual(['b', 'c'])
  })

  it('selects all calendars of a folder and its subfolders', () => {
    const store = useCalendarStore()
    store.folders = [folder('a'), folder('b', 'a')]
    store.items = [calendarItem('x'), calendarItem('y', 'a'), calendarItem('z', 'b')]
    store.select('a')
    expect(store.selectedCalendarIds.sort()).toEqual(['y', 'z'])
    store.select(ALL_CALENDARS)
    expect(store.selectedCalendarIds).toHaveLength(3)
  })

  it('survives cyclic folder data', () => {
    const store = useCalendarStore()
    store.folders = [folder('a', 'b'), folder('b', 'a')]
    expect(store.descendantFolderIds('a')).toEqual(['b'])
  })

  it('applies only the latest of overlapping loads', async () => {
    const store = useCalendarStore()
    const first = deferred<api.CalendarListItem[]>()
    const second = deferred<api.CalendarListItem[]>()
    vi.mocked(api.listCalendars).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    vi.mocked(api.listFolders).mockResolvedValue([])

    const firstLoad = store.load()
    const secondLoad = store.load()
    second.resolve([calendarItem('new')])
    await secondLoad
    first.resolve([calendarItem('old')])
    await firstLoad

    expect(store.items.map((i) => i.calendar.id)).toEqual(['new'])
  })

  it('builds the URL of a selection', () => {
    const store = useCalendarStore()
    store.folders = [folder('f')]
    expect(store.selectionPath(ALL_CALENDARS)).toBe('/calendar')
    expect(store.selectionPath('f')).toBe('/calendar/folder/f')
    expect(store.selectionPath('c')).toBe('/calendar/c')
  })

  it('reports once calendars are loaded, until the session is reset', async () => {
    const store = useCalendarStore()
    vi.mocked(api.listCalendars).mockResolvedValue([])
    vi.mocked(api.listFolders).mockResolvedValue([])
    expect(store.loaded).toBe(false)
    await store.load()
    expect(store.loaded).toBe(true)
    store.reset()
    expect(store.loaded).toBe(false)
  })
})
