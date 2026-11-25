import type { Overlay } from '.'
import type { MessageSchema } from '../en'

const emailNotifications: Overlay<MessageSchema['emailNotifications']> = {
  description:
    'Wähle, welche Benachrichtigungen zusätzlich per E-Mail an {email} kommen. In der App siehst du sie immer.',
  invitationsHelp:
    'Einladungen zu Terminen, ihre Änderungen und Absagen, mit dem Termin als Anhang für dein Mailprogramm.',
  responses: 'Antworten auf deine Einladungen',
  responsesHelp: 'Wenn Teilnehmende einen Termin zusagen oder absagen, den du organisierst.',
  approvalsHelp: 'Buchungen, die auf deine Entscheidung warten, und stornierte Buchungen.',
  decisions: 'Entscheidungen über deine Buchungen',
  decisionsHelp: 'Wenn deine Buchungen genehmigt oder abgelehnt werden.',
  commentsHelp: 'Neue Kommentare zu Terminen, die du erstellt oder kommentiert hast.',
  membershipsHelp: 'Wenn du zu einem Kalender hinzugefügt wirst.',
  role_changesHelp: 'Wenn du in einem Kalender eine Rolle mit mehr Rechten bekommst.',
  remindersHelp: 'Deine Terminerinnerungen, zusätzlich per E-Mail.',
}

export default emailNotifications
