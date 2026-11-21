import { describe, expect, it } from 'vitest'
import type { Occurrence } from '@/api'
import { groupByDay, isPast, matchesSearch } from '../agenda'

function occurrence(fields: Partial<Occurrence>): Occurrence {
  return {
    event_id: fields.title ?? 'event',
    calendar_id: 'cal',
    title: 'Event',
    description: '',
    start: '',
    end: '',
    all_day: false,
    recurrence_count: null,
    status: 'confirmed',
    category_id: null,
    category_name: null,
    category_color: null,
    resource_id: null,
    resource_name: null,
    resource_icon: '',
    location: '',
    location_resource_id: null,
    location_resource_icon: '',
    creator_id: 'user',
    can_edit: true,
    is_recurring: false,
    series_id: null,
    recurrence_id: null,
    ...fields,
  }
}

const local = (day: number, hour = 0, minute = 0) => new Date(2026, 9, day, hour, minute).toISOString()
const october = [new Date(2026, 9, 1), new Date(2026, 10, 1)] as const
const summary = (occurrences: Occurrence[]) =>
  groupByDay(occurrences, ...october).map((day) => [
    day.key,
    day.entries.map((entry) => `${entry.occurrence.title}:${entry.span}`),
  ])

describe('groupByDay', () => {
  it('lists days in order, all-day events first, then by start', () => {
    const occurrences = [
      occurrence({ title: 'Late', start: local(12, 15), end: local(12, 16) }),
      occurrence({ title: 'Early', start: local(12, 9), end: local(12, 10) }),
      occurrence({ title: 'Holiday', start: '2026-10-12T00:00:00Z', end: '2026-10-13T00:00:00Z', all_day: true }),
      occurrence({ title: 'Before', start: local(3, 8), end: local(3, 9) }),
    ]
    expect(summary(occurrences)).toEqual([
      ['2026-10-03', ['Before:single']],
      ['2026-10-12', ['Holiday:single', 'Early:single', 'Late:single']],
    ])
  })

  it('shows events over several days on each of their days within the range', () => {
    const trip = occurrence({
      title: 'Trip',
      start: '2026-10-30T00:00:00Z',
      end: '2026-11-03T00:00:00Z',
      all_day: true,
    })
    const night = occurrence({ title: 'Night', start: local(5, 22), end: local(6, 6) })
    expect(summary([trip, night])).toEqual([
      ['2026-10-05', ['Night:first']],
      ['2026-10-06', ['Night:last']],
      ['2026-10-30', ['Trip:first']],
      ['2026-10-31', ['Trip:middle']],
    ])
    expect(groupByDay([trip], ...october).at(-1)!.entries[0]).toMatchObject({ dayIndex: 2, dayCount: 4 })
  })

  it('ends a timed event at midnight on the day before', () => {
    expect(summary([occurrence({ title: 'Evening', start: local(7, 20), end: local(8) })])).toEqual([
      ['2026-10-07', ['Evening:single']],
    ])
  })

  it('leaves out days before the range', () => {
    const conference = occurrence({
      title: 'Conf',
      start: '2026-09-29T00:00:00Z',
      end: '2026-10-02T00:00:00Z',
      all_day: true,
    })
    expect(summary([conference])).toEqual([['2026-10-01', ['Conf:last']]])
  })
})

describe('matchesSearch', () => {
  const meeting = occurrence({ title: 'Team meeting', location: 'Room 4', category_name: 'Work' })

  it('matches every word anywhere, ignoring case', () => {
    expect(matchesSearch(meeting, '')).toBe(true)
    expect(matchesSearch(meeting, 'team ROOM')).toBe(true)
    expect(matchesSearch(meeting, 'work')).toBe(true)
    expect(matchesSearch(meeting, 'team kitchen')).toBe(false)
  })
})

describe('isPast', () => {
  it('ends all-day events at the end of their last day', () => {
    const day = occurrence({ start: '2026-10-12T00:00:00Z', end: '2026-10-13T00:00:00Z', all_day: true })
    expect(isPast(day, new Date(2026, 9, 12, 23))).toBe(false)
    expect(isPast(day, new Date(2026, 9, 13))).toBe(true)
  })

  it('ends timed events at their end', () => {
    const call = occurrence({ start: local(12, 9), end: local(12, 10) })
    expect(isPast(call, new Date(2026, 9, 12, 9, 30))).toBe(false)
    expect(isPast(call, new Date(2026, 9, 12, 10))).toBe(true)
  })
})
