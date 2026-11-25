import de from '../de'
import type { MessageSchema } from '../en'
import app from './app'
import auth from './auth'
import availability from './availability'
import emailNotifications from './emailNotifications'
import event from './event'
import notifications from './notifications'
import reminders from './reminders'
import rsvp from './rsvp'
import unsubscribe from './unsubscribe'

/** Some of the texts of `T`, with the same keys. */
export type Overlay<T> = { [K in keyof T]?: T[K] extends string ? string : Overlay<T[K]> }

type Messages = { [key: string]: string | Messages }

function overlay(base: Messages, changes: Messages): Messages {
  return Object.fromEntries(
    Object.entries(base).map(([key, text]) => {
      const change = changes[key]
      if (change === undefined) return [key, text]
      return [key, typeof text === 'string' || typeof change === 'string' ? change : overlay(text, change)]
    }),
  )
}

// The German that says "du": only the texts that address the reader (Sie, Ihr, imperatives); the
// rest are the formal German's (de), so the two don't drift apart.
export const changes: Overlay<MessageSchema> = {
  app,
  auth,
  availability,
  emailNotifications,
  event,
  notifications,
  reminders,
  rsvp,
  unsubscribe,
}

// The keys are the formal German's, so the result has every one of them.
const deInformal = overlay(de, changes) as MessageSchema

export default deInformal
