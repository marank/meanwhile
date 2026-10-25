import { describe, expect, it } from 'vitest'
import type * as api from '@/api'
import { event } from '@/components/event/__tests__/helpers'
import { browserTimeZone } from '@/services/datetime'
import { useEventForm } from '../useEventForm'

const place = (requiresApproval: boolean) =>
  ({ id: 'l1', label: 'Main hall', meta: { requires_approval: requiresApproval } }) as unknown as api.SearchResult

describe('useEventForm', () => {
  it('gives an event back as it was loaded', () => {
    const f = useEventForm()
    f.fillFromEvent(event({ category_id: 'k1', resource_id: 'r1', location: 'Room 1' }), false)
    expect(f.form.startTime).toBe(new Date('2026-03-10T09:00:00.000Z').toTimeString().slice(0, 5))
    expect(f.eventInput()).toEqual({
      title: 'Planning',
      description: 'Agenda',
      start: '2026-03-10T09:00:00.000Z',
      end: '2026-03-10T10:00:00.000Z',
      all_day: false,
      timezone: browserTimeZone(),
      show_recurrence_count: false,
      rrule: null,
      category_id: 'k1',
      resource_id: 'r1',
      location: 'Room 1',
      location_resource_id: null,
    })
    expect(f.bookedResourceIds.value).toEqual(['r1'])
  })

  it('takes all-day events by their UTC dates, the last day included', () => {
    const f = useEventForm()
    f.fillFromEvent(event({ all_day: true, start: '2026-03-10T00:00:00Z', end: '2026-03-12T00:00:00Z' }), false)
    expect([f.form.startDate, f.form.endDate]).toEqual(['2026-03-10', '2026-03-12'])
    expect(f.slot.value).toEqual({ start: new Date(2026, 2, 10), end: new Date(2026, 2, 13) })
    expect(f.eventInput()).toMatchObject({
      start: '2026-03-10T00:00:00.000Z',
      end: '2026-03-12T00:00:00.000Z',
      all_day: true,
    })
  })

  it('makes an event all-day where the calendar takes no other', () => {
    const f = useEventForm()
    f.fillFromEvent(event({ start: '2026-03-10T09:00:00Z' }), true)
    expect(f.form.allDay).toBe(true)
    expect(f.form.startDate).toBe('2026-03-10')
  })

  it('shows the opened occurrence of a series, whose all-day end is exclusive', () => {
    const f = useEventForm()
    f.fillFromEvent(event({ all_day: true, start: '2026-03-10T00:00:00Z', end: '2026-03-10T00:00:00Z' }), false)
    f.fillFromOccurrence({ recurrenceId: 'x', start: '2026-03-17T00:00:00Z', end: '2026-03-19T00:00:00Z' })
    expect([f.form.startDate, f.form.endDate]).toEqual(['2026-03-17', '2026-03-18'])

    const timed = useEventForm()
    timed.fillFromOccurrence({ recurrenceId: 'x', start: '2026-03-17T09:00:00Z', end: '2026-03-17T10:30:00Z' })
    expect(timed.slot.value).toEqual({ start: new Date('2026-03-17T09:00:00Z'), end: new Date('2026-03-17T10:30:00Z') })
  })

  it('starts a new event an hour long, or over the range given', () => {
    const f = useEventForm()
    f.fillDefaults(new Date(2026, 2, 10, 9), undefined, false)
    expect([f.form.startDate, f.form.startTime, f.form.endDate, f.form.endTime]).toEqual([
      '2026-03-10',
      '09:00',
      '2026-03-10',
      '10:00',
    ])
    f.fillDefaults(new Date(2026, 2, 10), new Date(2026, 2, 12), true)
    expect([f.form.allDay, f.form.endDate]).toEqual([true, '2026-03-12'])
  })

  it('finds an end before the start', () => {
    const f = useEventForm()
    expect(f.endBeforeStart.value).toBe(false)
    f.fillDefaults(new Date(2026, 2, 10, 9), undefined, false)
    f.form.endTime = '08:00'
    expect(f.endBeforeStart.value).toBe(true)
    f.form.allDay = true
    expect(f.endBeforeStart.value).toBe(false)
    f.form.endDate = '2026-03-09'
    expect(f.endBeforeStart.value).toBe(true)
  })

  it('sends an unchanged rule back as it was written, and a changed one as the editor writes it', () => {
    const f = useEventForm()
    f.fillFromEvent(event({ show_recurrence_count: true }), false)
    f.loadRrule('FREQ=WEEKLY;INTERVAL=1;BYDAY=TU')
    expect(f.eventInput()).toMatchObject({ rrule: 'FREQ=WEEKLY;INTERVAL=1;BYDAY=TU', show_recurrence_count: true })
    f.recurrence.value!.interval = 2
    expect(f.eventInput().rrule).toContain('INTERVAL=2')
    f.recurrence.value = null
    expect(f.eventInput()).toMatchObject({ rrule: null, show_recurrence_count: false })
  })

  it("keeps a rule the editor can't show", () => {
    const f = useEventForm()
    f.fillFromEvent(event(), false)
    f.loadRrule('FREQ=HOURLY')
    expect(f.recurrence.value).toBeNull()
    expect(f.foreignRrule.value).toBe('FREQ=HOURLY')
    expect(f.eventInput().rrule).toBe('FREQ=HOURLY')
  })

  it('books a suggested place, while typed text is just where the event is', () => {
    const f = useEventForm()
    f.fillDefaults(new Date(2026, 2, 10, 9), undefined, false)
    f.onLocationSelect('l1', place(true))
    expect([f.form.location, f.form.locationResourceId]).toEqual(['Main hall', 'l1'])
    expect(f.locationRequiresApproval.value).toBe(true)
    f.onLocationSelect('In the park', null)
    expect([f.form.location, f.form.locationResourceId]).toEqual(['In the park', null])
    expect(f.locationRequiresApproval.value).toBe(false)
    f.onLocationSelect(null, null)
    expect(f.eventInput().location).toBeNull()
  })

  it('tells when the resource picked needs approval', () => {
    const f = useEventForm()
    f.onResourceSelect('r1', place(true))
    expect(f.resourceRequiresApproval.value).toBe(true)
    f.onResourceSelect(null, null)
    expect(f.resourceRequiresApproval.value).toBe(false)
  })
})
