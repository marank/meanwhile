import type { MessageSchema } from '../en'

const emailNotifications: MessageSchema['emailNotifications'] = {
  title: 'E-Mail-Benachrichtigungen',
  description:
    'Wählen Sie, welche Benachrichtigungen zusätzlich per E-Mail an {email} kommen. In der App sehen Sie sie immer.',
  invitations: 'Einladungen',
  invitationsHelp:
    'Einladungen zu Terminen, ihre Änderungen und Absagen, mit dem Termin als Anhang für Ihr Mailprogramm.',
  responses: 'Antworten auf Ihre Einladungen',
  responsesHelp: 'Wenn Teilnehmende einen Termin zusagen oder absagen, den Sie organisieren.',
  approvals: 'Genehmigungsanfragen',
  approvalsHelp: 'Buchungen, die auf Ihre Entscheidung warten, und stornierte Buchungen.',
  decisions: 'Entscheidungen über Ihre Buchungen',
  decisionsHelp: 'Wenn Ihre Buchungen genehmigt oder abgelehnt werden.',
  comments: 'Kommentare',
  commentsHelp: 'Neue Kommentare zu Terminen, die Sie erstellt oder kommentiert haben.',
  memberships: 'Kalenderzugriff',
  membershipsHelp: 'Wenn Sie zu einem Kalender hinzugefügt werden.',
  role_changes: 'Mehr Rechte in einem Kalender',
  role_changesHelp: 'Wenn Sie in einem Kalender eine Rolle mit mehr Rechten bekommen.',
  reminders: 'Erinnerungen',
  remindersHelp: 'Ihre Terminerinnerungen, zusätzlich per E-Mail.',
}

export default emailNotifications
