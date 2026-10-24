import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { User } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { formatCalendarDate, formatDate, toDateInputValue, toTimeInputValue } from '../datetime'

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
