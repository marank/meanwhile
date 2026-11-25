import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { User } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { i18n } from '@/i18n'
import {
  daysAgo,
  formatCalendarDate,
  formatDate,
  formatTimeAgo,
  newEventStart,
  toDateInputValue,
  toTimeInputValue,
} from '../datetime'

describe('date input values', () => {
  it('use the local date and time', () => {
    const date = new Date(2026, 0, 5, 7, 3)
    expect(toDateInputValue(date)).toBe('2026-01-05')
    expect(toTimeInputValue(date)).toBe('07:03')
  })
})

describe('formatDate', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('follows the user preference', () => {
    const auth = useAuthStore()
    const date = new Date(2026, 11, 31)
    for (const [format, expected] of [
      ['dmy', '31.12.2026'],
      ['mdy', '12/31/2026'],
      ['ymd', '2026-12-31'],
    ] as const) {
      auth.user = { date_format: format } as User
      expect(formatDate(date)).toBe(expected)
    }
  })
})

describe('formatCalendarDate', () => {
  it('shows the day an all-day value names, whatever the time zone', () => {
    // formatDate of a local date that the UTC midnight would shift west of UTC.
    expect(formatCalendarDate('2026-01-05T00:00:00Z')).toBe(formatDate(new Date(2026, 0, 5)))
    expect(formatCalendarDate('2026-01-05')).toBe(formatDate(new Date(2026, 0, 5)))
  })
})

describe('formatTimeAgo', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'en'
  })

  const now = new Date(2026, 0, 5, 9, 30)

  it('says how long ago, coarser the longer it was', () => {
    expect(formatTimeAgo(new Date(2026, 0, 5, 9, 29, 30), now)).toBe('just now')
    expect(formatTimeAgo(new Date(2026, 0, 5, 9, 25), now)).toBe('5 min. ago')
    expect(formatTimeAgo(new Date(2026, 0, 5, 6, 0), now)).toBe('3 hr. ago')
    expect(formatTimeAgo(new Date(2026, 0, 4, 23, 0), now)).toBe('yesterday')
    expect(formatTimeAgo(new Date(2026, 0, 1, 12, 0), now)).toBe('4 days ago')
    expect(formatTimeAgo(new Date(2025, 11, 20, 12, 0), now)).toMatch(/2025/)
  })

  it('speaks the language of the app', () => {
    i18n.global.locale.value = 'de'
    expect(formatTimeAgo(new Date(2026, 0, 5, 9, 25), now)).toBe('vor 5 Min.')
    expect(formatTimeAgo(new Date(2026, 0, 5, 9, 29, 59), now)).toBe('gerade eben')
  })

  it('counts calendar days, not 24 hours', () => {
    expect(daysAgo(new Date(2026, 0, 4, 23, 59), new Date(2026, 0, 5, 0, 1))).toBe(1)
    expect(daysAgo(new Date(2026, 0, 5, 0, 1), new Date(2026, 0, 5, 23, 59))).toBe(0)
  })
})

describe('newEventStart', () => {
  const at = (hour: number, minute = 0) => new Date(2026, 10, 25, hour, minute)

  it('starts other days at the start of the working day', () => {
    expect(newEventStart(new Date(2026, 10, 26), at(14, 20))).toEqual(new Date(2026, 10, 26, 9))
    expect(newEventStart(new Date(2026, 10, 24), at(14, 20))).toEqual(new Date(2026, 10, 24, 9))
  })

  it('starts today at the next full hour, not before the working day and still today', () => {
    expect(newEventStart(new Date(2026, 10, 25), at(14, 20))).toEqual(at(15))
    expect(newEventStart(new Date(2026, 10, 25), at(6, 30))).toEqual(at(9))
    expect(newEventStart(new Date(2026, 10, 25), at(23, 30))).toEqual(at(23))
  })
})
