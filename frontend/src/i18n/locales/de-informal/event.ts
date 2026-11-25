import type { Overlay } from '.'
import type { MessageSchema } from '../en'

const event: Overlay<MessageSchema['event']> = {
  notFound: 'Diesen Termin gibt es nicht mehr, oder du kannst ihn nicht sehen.',
}

export default event
