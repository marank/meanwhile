import type { Overlay } from '.'
import type { MessageSchema } from '../en'

const availability: Overlay<MessageSchema['availability']> = {
  noOne: 'Füge Teilnehmende oder eine Ressource hinzu, um deren Verfügbarkeit zu sehen.',
}

export default availability
