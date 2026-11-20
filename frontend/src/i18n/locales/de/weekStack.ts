import type { MessageSchema } from '../en'

const weekStack: MessageSchema['weekStack'] = {
  minutes: '{n} Min.',
  hours: '{n} Std.',
  hoursMinutes: '{h} Std. {m} Min.',
}

export default weekStack
