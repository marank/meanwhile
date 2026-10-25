import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api'
import { confirm } from '@/services/dialog'
import { bookingErrorMessage } from '@/services/errors'
import { chooseScope, type OccurrenceRef } from '@/services/occurrences'
import type { useEventParticipants, useEventReminders } from './useEventExtras'

/**
 * What the event dialog sends: saving (with its participants and reminders, of a series asking which
 * occurrences it applies to), deleting, and deciding on a booking. One at a time; a failure shows in `error`.
 */
export function useEventSave(options: {
  /** The calendar the event is in, or is created in. */
  calendar: Ref<api.Calendar | null>
  /** The event edited; becomes the created one once a new event is saved. */
  event: Ref<api.Event | null>
  /** The event the dialog was opened for. */
  eventId: () => string | null | undefined
  /** The occurrence of a series that was opened. */
  seriesOccurrence: Ref<OccurrenceRef | null>
  /** A changed occurrence of a series. */
  isException: Ref<boolean>
  /** Whether the user may change the event; otherwise only their own reminders are saved. */
  canModify: Ref<boolean>
  /** Whether what is entered can be saved. */
  valid: () => boolean
  eventInput: () => api.EventInput
  participants: ReturnType<typeof useEventParticipants>
  reminders: ReturnType<typeof useEventReminders>
  onSaved: () => void
  onDeleted: () => void
}) {
  const { event, participants, reminders } = options
  const { t } = useI18n()
  const busy = ref(false)
  const error = ref('')

  async function submit(action: () => Promise<unknown>, done: () => void) {
    if (busy.value) return
    busy.value = true
    error.value = ''
    try {
      await action()
      done()
    } catch (e) {
      error.value = bookingErrorMessage(e)
    } finally {
      busy.value = false
    }
  }

  async function save() {
    const target = options.calendar.value
    if (!target || !options.valid() || busy.value) return
    const existing = event.value
    if (existing && !options.canModify.value) {
      // Who may not change the event may still set their own reminders.
      await submit(() => reminders.save(existing.id), options.onSaved)
      return
    }
    const occurrence = options.seriesOccurrence.value
    if (occurrence && existing) {
      const input = options.eventInput()
      // A new recurrence can't apply to a single occurrence.
      const scope = await chooseScope('edit', input.rrule === existing.rrule)
      if (!scope) return
      await submit(async () => {
        await api.updateOccurrence(existing.id, occurrence.recurrenceId, scope, input)
        await participants.save(existing.id)
        await reminders.save(existing.id)
      }, options.onSaved)
      return
    }
    await submit(async () => {
      if (existing) {
        await api.updateEvent(existing.id, options.eventInput())
        await participants.save(existing.id)
        await reminders.save(existing.id)
      } else {
        const created = await api.createEvent(target.id, {
          ...options.eventInput(),
          participants: participants.pending.value.map(({ user_id, email, status }) => ({ user_id, email, status })),
        })
        // From now on the dialog edits the created event, so saving again after a failed step
        // below doesn't create it twice.
        event.value = created
        participants.pending.value = []
        await reminders.save(created.id)
      }
    }, options.onSaved)
  }

  async function remove() {
    const eventId = options.eventId()
    if (!eventId) return
    const occurrence = options.seriesOccurrence.value
    if (occurrence) {
      const scope = await chooseScope('delete')
      if (!scope) return
      await submit(() => api.deleteOccurrence(eventId, occurrence.recurrenceId, scope), options.onDeleted)
      return
    }
    const text = options.isException.value ? t('series.deleteExceptionText') : t('app.deleteEventText')
    if (!(await confirm(text, t('app.deleteEventTitle')))) return
    await submit(() => api.deleteEvent(eventId), options.onDeleted)
  }

  /** Approves or rejects a booking, with an optional note to the one who booked. */
  async function decide(action: 'approve' | 'reject', note: string) {
    const eventId = options.eventId()
    if (!eventId) return
    const trimmed = note.trim() || undefined
    await submit(
      () => (action === 'approve' ? api.approveEvent(eventId, trimmed) : api.rejectEvent(eventId, trimmed)),
      options.onSaved,
    )
  }

  return { busy, error, save, remove, decide }
}
