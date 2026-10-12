import { describe, expect, it } from 'vitest'
import { parseCalendarQuery, parseDate, showsTarget } from '../calendarUrl'

// "Today" is 12 October 2026.
const today = new Date(2026, 9, 12)
const parse = (query: Record<string, string | string[]>) => parseCalendarQuery(query, today)
const ymd = (date: Date | undefined) => date && [date.getFullYear(), date.getMonth() + 1, date.getDate()].join('-')

describe('parseCalendarQuery', () => {
  it('opens a month of this year with month', () => {
    expect(ymd(parse({ month: '3' }).date)).toBe('2026-3-1')
    expect(ymd(parse({ month: '12' }).date)).toBe('2026-12-1')
    expect(ymd(parse({ month: '03' }).date)).toBe('2026-3-1')
  })

  it('opens this month of a year with year', () => {
    expect(ymd(parse({ year: '2025' }).date)).toBe('2025-10-1')
    expect(ymd(parse({ year: '2031' }).date)).toBe('2031-10-1')
  })

  it('opens that month of that year with both', () => {
    expect(ymd(parse({ month: '2', year: '2024' }).date)).toBe('2024-2-1')
  })

  it('opens the month of a date, or a month given as year and month', () => {
    expect(ymd(parse({ date: '2026-10-01' }).date)).toBe('2026-10-1')
    expect(ymd(parse({ date: '2027-03-15' }).date)).toBe('2027-3-15')
    expect(ymd(parse({ date: '2026-10' }).date)).toBe('2026-10-1')
    expect(ymd(parse({ date: '2026-1-5' }).date)).toBe('2026-1-5')
  })

  it('lets date win over month and year', () => {
    expect(ymd(parse({ date: '2026-10-01', month: '3', year: '2020' }).date)).toBe('2026-10-1')
  })

  it('reads the view', () => {
    expect(parse({ view: 'week' }).view).toBe('week')
    expect(parse({ view: 'month' }).view).toBe('month')
    expect(parse({ view: 'list' }).view).toBe('list')
    expect(parse({ view: 'week', month: '3' })).toEqual({ view: 'week', date: new Date(2026, 2, 1) })
    expect(parse({})).toEqual({})
  })

  it('ignores values that make no sense, and keeps the valid ones', () => {
    expect(parse({ month: '13' })).toEqual({})
    expect(parse({ month: '0' })).toEqual({})
    expect(parse({ month: 'abc' })).toEqual({})
    expect(parse({ year: '25' })).toEqual({})
    expect(parse({ year: '20255' })).toEqual({})
    expect(parse({ date: '2026-02-30' })).toEqual({})
    expect(parse({ date: '2026-13' })).toEqual({})
    expect(parse({ date: 'yesterday' })).toEqual({})
    expect(parse({ view: 'day' })).toEqual({})
    // One bad value doesn't take the others down.
    expect(ymd(parse({ month: '13', year: '2025' }).date)).toBe('2025-10-1')
    expect(ymd(parse({ date: 'nope', month: '5' }).date)).toBe('2026-5-1')
    expect(parse({ view: 'day', month: '5' }).view).toBeUndefined()
  })

  it('takes the first of a repeated parameter, and copes with leap days', () => {
    expect(ymd(parse({ month: ['4', '5'] }).date)).toBe('2026-4-1')
    expect(ymd(parse({ date: '2028-02-29' }).date)).toBe('2028-2-29')
    expect(parse({ date: '2027-02-29' })).toEqual({})
  })
})

describe('week', () => {
  it('opens that ISO week of this year as a week', () => {
    // Week 50 of 2026 runs from Monday 7 December.
    expect(parse({ week: '50' })).toEqual({ view: 'week', date: new Date(2026, 11, 7) })
    expect(ymd(parse({ week: '1' }).date)).toBe('2025-12-29')
    expect(ymd(parse({ week: '53' }).date)).toBe('2026-12-28')
  })

  it('takes the year from year, and a month view if asked for', () => {
    expect(ymd(parse({ week: '10', year: '2024' }).date)).toBe('2024-3-4')
    expect(parse({ week: '10', view: 'month' }).view).toBe('month')
  })

  it('ignores weeks the year does not have, and yields to date', () => {
    expect(parse({ week: '53', year: '2025' }).view).toBeUndefined()
    expect(parse({ week: '0' })).toEqual({})
    expect(parse({ week: '54' })).toEqual({})
    expect(ymd(parse({ week: '50', date: '2026-02-03' }).date)).toBe('2026-2-3')
    expect(ymd(parse({ week: '50', month: '3' }).date)).toBe('2026-12-7')
    expect(ymd(parse({ week: 'x', month: '3' }).date)).toBe('2026-3-1')
  })
})

describe('parseDate', () => {
  it('needs a four-digit year', () => {
    expect(parseDate('26-10-01')).toBeUndefined()
    expect(parseDate(undefined)).toBeUndefined()
    expect(parseDate('')).toBeUndefined()
  })
})

describe('showsTarget', () => {
  const october = [new Date(2026, 9, 1), new Date(2026, 10, 1)] as const
  it('is true when the shown range contains the date and the view fits', () => {
    expect(showsTarget({ date: new Date(2026, 9, 15) }, 'month', ...october)).toBe(true)
    expect(showsTarget({ date: new Date(2026, 9, 1), view: 'month' }, 'month', ...october)).toBe(true)
    expect(showsTarget({}, 'month', ...october)).toBe(true)
  })

  it('is false for another month, another view, or the end of the range', () => {
    expect(showsTarget({ date: new Date(2026, 10, 1) }, 'month', ...october)).toBe(false)
    expect(showsTarget({ date: new Date(2026, 8, 30) }, 'month', ...october)).toBe(false)
    expect(showsTarget({ view: 'week' }, 'month', ...october)).toBe(false)
  })
})
