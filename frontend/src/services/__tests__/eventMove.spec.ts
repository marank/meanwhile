import { describe, expect, it } from 'vitest'
import { browserTimeZone } from '../datetime'
import { movedTimes } from '../eventMove'

describe('movedTimes', () => {
  it('saves a timed event at its new times, an hour long when FullCalendar gives no end', () => {
    const start = new Date(2026, 9, 14, 10)
    expect(movedTimes({ start, end: new Date(2026, 9, 14, 12, 30), allDay: false })).toEqual({
      start: start.toISOString(),
      end: new Date(2026, 9, 14, 12, 30).toISOString(),
      all_day: false,
      timezone: browserTimeZone(),
    })
    expect(movedTimes({ start, end: null, allDay: false }).end).toBe(new Date(2026, 9, 14, 11).toISOString())
  })

  it('saves all-day events as UTC midnights with the last day included', () => {
    expect(movedTimes({ start: new Date(2026, 9, 14), end: new Date(2026, 9, 17), allDay: true })).toMatchObject({
      start: '2026-10-14T00:00:00.000Z',
      end: '2026-10-16T00:00:00.000Z',
      all_day: true,
    })
    // A single day: FullCalendar may leave out the end.
    expect(movedTimes({ start: new Date(2026, 9, 14), end: null, allDay: true })).toMatchObject({
      start: '2026-10-14T00:00:00.000Z',
      end: '2026-10-14T00:00:00.000Z',
    })
  })

  it('takes the day before by the calendar, also over a change of clocks', () => {
    // 29 March 2026 has 23 hours in Central Europe; the end is still the 29th.
    expect(movedTimes({ start: new Date(2026, 2, 28), end: new Date(2026, 2, 30), allDay: true }).end).toBe(
      '2026-03-29T00:00:00.000Z',
    )
  })
})
