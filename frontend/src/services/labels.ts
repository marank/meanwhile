import type { AppNotification, NotificationType, ParticipantStatus } from '@/api'
import { i18n } from '@/i18n'
import { reminderText } from './reminders'

export const participantStatuses: ParticipantStatus[] = ['needs_action', 'accepted', 'declined', 'tentative']

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
  const actor = notification.actor_name || notification.data?.name || notification.data?.email || t('app.someone')
  if (notification.type === 'participant_replied') {
    const status = notification.data?.status as ParticipantStatus | undefined
    return t(status ? replyKeys[status] : key, { actor, title: notification.title })
  }
  return t(key, { actor, title: notification.title })
}
