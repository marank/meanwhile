import type { Overlay } from '.'
import type { MessageSchema } from '../en'

const reminders: Overlay<MessageSchema['reminders']> = {
  hint: 'Erinnerungen gelten nur für dich, bei Serien für jeden Termin.',
}

export default reminders
