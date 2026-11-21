import type { AppNotification, NotificationType, ParticipantStatus } from '@/api'
import { i18n } from '@/i18n'
import { allValues } from '@/utils/enums'
import { formatDayMonth, weekdayName } from './datetime'
import { reminderText } from './reminders'
import { nonEmpty } from './text'
import { matchingPreset, parseRrule, recurrenceDefaults, type RecurrencePreset } from './rrule'

export const participantStatuses = allValues<ParticipantStatus>({
  needs_action: true,
  accepted: true,
  declined: true,
  tentative: true,
})

const participantStatusKeys: Record<ParticipantStatus, string> = {
  needs_action: 'event.statusNeedsAction',
  accepted: 'event.statusAccepted',
  declined: 'event.statusDeclined',
  tentative: 'event.statusTentative',
}

export function participantStatusLabel(status: ParticipantStatus): string {
  return i18n.global.t(participantStatusKeys[status])
}

// A Record over the union makes the compiler point out notification types without a text.
const notificationKeys: Record<NotificationType, string> = {
  approval_requested: 'notifications.approvalRequested',
  booking_approved: 'notifications.bookingApproved',
  booking_rejected: 'notifications.bookingRejected',
  booking_cancelled: 'notifications.bookingCancelled',
  participant_added: 'notifications.participantAdded',
  member_added: 'notifications.memberAdded',
  member_role_changed: 'notifications.memberRoleChanged',
  comment_added: 'notifications.commentAdded',
  event_reminder: 'reminders.due',
  participant_replied: 'notifications.participantReplied',
}

const replyKeys: Record<ParticipantStatus, string> = {
  accepted: 'notifications.participantAccepted',
  tentative: 'notifications.participantTentative',
  declined: 'notifications.participantDeclined',
  needs_action: 'notifications.participantReplied',
}

export function notificationText(notification: AppNotification): string {
  const { t } = i18n.global
  const key = notificationKeys[notification.type]
  // Types added on the server before the client knows them fall back to the raw title.
  if (!key) return notification.title
  if (notification.type === 'event_reminder' && notification.data?.start) {
    return reminderText(notification.title, notification.data.start, !!notification.data.all_day)
  }
  // Participants without an account answer by email or link; they are named by their address.
  const actor =
    nonEmpty(notification.actor_name) ??
    nonEmpty(notification.data?.name) ??
    nonEmpty(notification.data?.email) ??
    t('app.someone')
  if (notification.type === 'participant_replied') {
    const status = notification.data?.status
    return t(status ? replyKeys[status] : key, { actor, title: notification.title })
  }
  return t(key, { actor, title: notification.title })
}

const ORDINAL_KEYS: Record<number, string> = { 1: 'first', 2: 'second', 3: 'third', 4: 'fourth', [-1]: 'last' }

/** A recurrence preset's name for a series starting on `start`, e.g. "Weekly on Monday". */
export function recurrencePresetLabel(preset: RecurrencePreset, start: Date): string {
  const { t } = i18n.global
  const { weekday, monthDay, ordinal } = recurrenceDefaults(start)
  switch (preset) {
    case 'daily':
      return t('recurrence.daily')
    case 'weekdays':
      return t('recurrence.weekdays')
    case 'weekly':
      return t('recurrence.weekly', { weekday: weekdayName(weekday) })
    case 'biweekly':
      return t('recurrence.biweekly', { weekday: weekdayName(weekday) })
    case 'monthlyDate':
      return t('recurrence.monthlyDate', { day: monthDay })
    case 'monthlyWeekday':
      return t('recurrence.monthlyWeekday', {
        ordinal: t(`recurrence.ordinal.${ORDINAL_KEYS[ordinal]}`),
        weekday: weekdayName(weekday),
      })
    case 'yearly':
      return t('recurrence.yearly', { date: formatDayMonth(start) })
  }
}

/** How a series starting on `start` repeats, in words: its preset's name, or "Repeats" for other rules. */
export function recurrenceSummary(rrule: string, start: Date): string {
  const defaults = recurrenceDefaults(start)
  const rule = parseRrule(rrule, defaults)
  const preset = rule && matchingPreset(rule, defaults)
  return preset ? recurrencePresetLabel(preset, start) : i18n.global.t('rsvp.repeats')
}
