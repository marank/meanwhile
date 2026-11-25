import { computed, ref } from 'vue'
import * as api from '@/api'
import type { PendingParticipant } from '@/components/event/EventParticipantsTab.vue'

/** A file or link added in the dialog; sent when the event is saved. */
export type PendingAttachment =
  | { tempId: string; kind: 'file'; name: string; file: File }
  | { tempId: string; kind: 'link'; name: string; url: string }

/** The current user's own reminders of an event, in minutes before the start; saved with the event. */
export function useEventReminders() {
  const minutes = ref<number[]>([])
  const valid = ref(true)
  let loaded = ''
  const changed = computed(() => minutes.value.join(',') !== loaded)

  // Reminders of a changed occurrence are those of its series.
  async function load(eventId: string) {
    const own = await api.getReminders(eventId).catch(() => ({ minutes: [] }))
    minutes.value = own.minutes
    loaded = minutes.value.join(',')
  }

  /** Saves the reminders for the event (of a series: for all occurrences) if they changed. */
  async function save(eventId: string) {
    if (changed.value) await api.setReminders(eventId, minutes.value)
  }

  return { minutes, valid, changed, load, save }
}

/** An event's participants: those saved, and those added and removed in the dialog until it is saved. */
export function useEventParticipants() {
  /** The saved participants, loaded once with the event. */
  const saved = ref<api.EventParticipant[] | null>(null)
  /** Participants added in the dialog; sent when the event is saved. */
  const pending = ref<PendingParticipant[]>([])
  /** Saved participants removed in the dialog; removed when the event is saved. */
  const removedIds = ref<string[]>([])

  /** Who takes part as the dialog shows it. */
  const current = computed(() => [
    ...(saved.value ?? []).filter((p) => !removedIds.value.includes(p.id)),
    ...pending.value,
  ])

  async function load(eventId: string) {
    saved.value = await api.listEventParticipants(eventId).catch(() => [])
  }

  /** Sends the participants added and removed in the dialog (of a series: for all occurrences).
   * Each one leaves its list once sent, so saving again after a failure sends only the rest. */
  async function save(eventId: string) {
    // Filtering replaces the lists, so the loops go on over the ones they started with.
    for (const id of removedIds.value) {
      await api.removeEventParticipant(eventId, id)
      removedIds.value = removedIds.value.filter((removed) => removed !== id)
    }
    for (const participant of pending.value) {
      const { user_id, email, status } = participant
      await api.addEventParticipant(eventId, user_id ? { user_id, status } : { email, status })
      pending.value = pending.value.filter((p) => p !== participant)
    }
  }

  return { saved, pending, removedIds, current, load, save }
}

/** An event's attachments: those saved, and those added and removed in the dialog until it is saved. */
export function useEventAttachments() {
  /** The saved attachments (of a series: its own), loaded with the event; null while loading. */
  const saved = ref<api.Attachment[] | null>(null)
  const pending = ref<PendingAttachment[]>([])
  const removedIds = ref<string[]>([])

  async function load(eventId: string) {
    saved.value = await api.listAttachments(eventId).catch(() => [])
  }

  /** Sends what was added and removed; each one leaves its list once sent, so saving again after a
   * failure (e.g. a file the server refused) sends only the rest. */
  async function save(eventId: string) {
    // Filtering replaces the lists, so the loops go on over the ones they started with.
    for (const id of removedIds.value) {
      await api.removeAttachment(eventId, id)
      removedIds.value = removedIds.value.filter((removed) => removed !== id)
    }
    for (const attachment of pending.value) {
      if (attachment.kind === 'file') await api.uploadAttachment(eventId, attachment.file)
      else await api.addAttachmentLink(eventId, { url: attachment.url, name: attachment.name })
      pending.value = pending.value.filter((p) => p !== attachment)
    }
  }

  return { saved, pending, removedIds, load, save }
}
