import type { AppNotification, NotificationType, ParticipantStatus } from '@/api'
import { i18n } from '@/i18n'

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
}

export function notificationText(notification: AppNotification): string {
  const { t } = i18n.global
  const key = notificationKeys[notification.type]
  // Types added on the server before the client knows them fall back to the raw title.
  if (!key) return notification.title
  return t(key, { actor: notification.actor_name || t('app.someone'), title: notification.title })
}
