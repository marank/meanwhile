import type { Overlay } from '.'
import type { MessageSchema } from '../en'

const notifications: Overlay<MessageSchema['notifications']> = {
  participantAdded: '{actor} hat dich zu „{title}“ eingeladen',
  memberAdded: '{actor} hat dich zu „{title}“ hinzugefügt',
  memberRoleChanged: '{actor} hat deine Rolle in „{title}“ geändert',
  participantReplied: '{actor} hat auf deine Einladung zu „{title}“ geantwortet',
  participantAccepted: '{actor} hat deine Einladung zu „{title}“ angenommen',
  participantTentative: '{actor} hat deine Einladung zu „{title}“ vorläufig angenommen',
  participantDeclined: '{actor} hat deine Einladung zu „{title}“ abgelehnt',
  yourAnswer: 'Deine Antwort: {answer}',
  openApprovals: 'Keine offenen Anfragen | 1 Anfrage wartet auf dich | {count} Anfragen warten auf dich',
  openInvitations:
    'Keine offenen Einladungen | 1 Einladung wartet auf deine Antwort | {count} Einladungen warten auf deine Antwort',
}

export default notifications
