import { vi } from 'vitest'
import type { Calendar, CalendarListItem, CalendarRole, Folder, Occurrence, OverviewSettings } from '@/api'
import { overviewPalette, paletteColors } from '@/services/calendarColors'

/** An ISO timestamp of a local time, as the API sends them. */
export function at(year: number, month: number, day: number, hour = 0, minute = 0): string {
  return new Date(year, month - 1, day, hour, minute).toISOString()
}

export function occurrence(overrides: Partial<Occurrence> = {}): Occurrence {
  return {
    event_id: 'e1',
    calendar_id: 'c1',
    title: 'Meeting',
    description: '',
    start: at(2026, 10, 14, 10),
    end: at(2026, 10, 14, 11),
    all_day: false,
    recurrence_count: null,
    status: 'confirmed',
    show_as: 'busy',
    category_id: null,
    category_name: null,
    category_color: null,
    resource_id: null,
    resource_name: null,
    resource_icon: '',
    location: '',
    location_resource_id: null,
    location_resource_icon: '',
    creator_id: 'u1',
    can_edit: true,
    is_recurring: false,
    series_id: null,
    recurrence_id: null,
    ...overrides,
  }
}

/** An all-day occurrence over the given local days, stored as UTC midnights with an inclusive end. */
export function allDay(first: string, last: string, overrides: Partial<Occurrence> = {}): Occurrence {
  return occurrence({ start: `${first}T00:00:00.000Z`, end: `${last}T00:00:00.000Z`, all_day: true, ...overrides })
}

export function calendar(id: string, overrides: Partial<Calendar> = {}): Calendar {
  return {
    id,
    name: `Calendar ${id}`,
    description: '',
    url_path: null,
    force_all_day: false,
    first_weekday: 1,
    show_weekends: true,
    weekend_days: [0, 6],
    show_week_numbers: false,
    ...paletteColors(overviewPalette),
    event_color: '#336699',
    dark_event_color: '#99bbdd',
    owner_id: 'u1',
    is_public: false,
    public_role: 'read',
    created_at: '',
    updated_at: '',
    my_membership: null,
    ...overrides,
  }
}

export function calendarItem(
  id: string,
  options: {
    role?: CalendarRole
    folderId?: string | null
    position?: number
    access?: CalendarListItem['access']
    calendar?: Partial<Calendar>
  } = {},
): CalendarListItem {
  return {
    calendar: calendar(id, options.calendar),
    membership: {
      id: `m-${id}`,
      calendar_id: id,
      user_id: 'u1',
      email: 'me@example.com',
      display_name: 'Me',
      role: options.role ?? 'owner',
      folder_id: options.folderId ?? null,
      position: options.position ?? 0,
    },
    access: options.access ?? 'member',
  }
}

export function folder(id: string, parentId: string | null = null, position = 0): Folder {
  return { id, name: `Folder ${id}`, parent_id: parentId, position }
}

export function overviewSettings(overrides: Partial<OverviewSettings> = {}): OverviewSettings {
  return {
    first_weekday: 1,
    show_weekends: true,
    weekend_days: [0, 6],
    show_week_numbers: false,
    use_calendar_colors: true,
    ...paletteColors(overviewPalette),
    event_color: '#aa0000',
    dark_event_color: '#ff8888',
    ...overrides,
  }
}

/**
 * jsdom has no matchMedia; this one answers `matches` for the queries listed and lets tests change them
 * later, as turning a phone would.
 */
export function stubMatchMedia(matching: string[] = []) {
  const lists = new Map<string, { matches: boolean; listeners: Set<(event: MediaQueryListEvent) => void> }>()
  const entry = (query: string) => {
    let list = lists.get(query)
    if (!list) {
      list = { matches: matching.includes(query), listeners: new Set() }
      lists.set(query, list)
    }
    return list
  }
  vi.stubGlobal('matchMedia', (query: string) => {
    const list = entry(query)
    return {
      get matches() {
        return list.matches
      },
      media: query,
      addEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) => list.listeners.add(listener),
      removeEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) =>
        list.listeners.delete(listener),
    }
  })
  return {
    set(query: string, matches: boolean) {
      const list = entry(query)
      list.matches = matches
      for (const listener of list.listeners) listener({ matches, media: query } as MediaQueryListEvent)
    },
  }
}
