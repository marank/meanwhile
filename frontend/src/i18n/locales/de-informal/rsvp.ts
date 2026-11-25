import type { Overlay } from '.'
import type { MessageSchema } from '../en'

const rsvp: Overlay<MessageSchema['rsvp']> = {
  yourTimeZone: 'Zeiten in deiner Zeitzone ({zone})',
  you: 'du',
  yourAnswer: 'Deine Antwort',
}

export default rsvp
