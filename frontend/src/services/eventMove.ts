import type { EventDropInfo, EventResizeDoneInfo } from '@fullcalendar/vue3'
import * as api from '@/api'
import type { Occurrence } from '@/api'
import { browserTimeZone, toDateInputValue } from './datetime'
import { alert } from './dialog'
import { bookingErrorMessage } from './errors'
import { chooseScope, seriesOccurrence } from './occurrences'

const HOUR_MS = 60 * 60 * 1000

/** The times an event dragged or resized in the calendar is saved with. */
export function movedTimes(event: { start: Date; end: Date | null; allDay: boolean }) {
  let start: string
  let end: string
  if (event.allDay) {
    // All-day events are stored as UTC midnights; FullCalendar's end is exclusive, the API's inclusive.
    start = `${toDateInputValue(event.start)}T00:00:00.000Z`
    // The day before by the calendar, not 24 hours earlier: the night clocks spring forward has 23.
    const lastDay = event.end ? new Date(event.end) : null
    lastDay?.setDate(lastDay.getDate() - 1)
    end = lastDay ? `${toDateInputValue(lastDay)}T00:00:00.000Z` : start
  } else {
    start = event.start.toISOString()
    end = (event.end ?? new Date(event.start.getTime() + HOUR_MS)).toISOString()
  }
  return { start, end, all_day: event.allDay, timezone: browserTimeZone() }
}

/**
 * Saves an event dragged or resized in the calendar (of a series: asking which occurrences it applies to).
 * Puts it back where it was when cancelled or refused; true when it was saved.
 */
export async function moveEvent(info: EventDropInfo | EventResizeDoneInfo): Promise<boolean> {
  const event = info.event
  if (!event.start) {
    info.revert()
    return false
  }
  const data = movedTimes({ start: event.start, end: event.end, allDay: event.allDay })
  const occ = event.extendedProps.occurrence as Occurrence
  const occurrence = seriesOccurrence(occ)
  try {
    if (occurrence) {
      const scope = await chooseScope('edit')
      if (!scope) {
        info.revert()
        return false
      }
      await api.updateOccurrence(occ.event_id, occurrence.recurrenceId, scope, data)
    } else {
      await api.updateEvent(occ.event_id, data)
    }
    return true
  } catch (error) {
    info.revert()
    await alert(bookingErrorMessage(error))
    return false
  }
}
