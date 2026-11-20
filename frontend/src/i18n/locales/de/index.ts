import type { MessageSchema } from '../en'
import app from './app'
import colorRole from './colorRole'
import recurrence from './recurrence'
import roles from './roles'
import auth from './auth'
import event from './event'
import availability from './availability'
import reminders from './reminders'
import weekStack from './weekStack'
import agenda from './agenda'
import series from './series'
import activity from './activity'
import notifications from './notifications'
import booking from './booking'
import palette from './palette'
import emailNotifications from './emailNotifications'
import unsubscribe from './unsubscribe'
import rsvp from './rsvp'

// Typed against the English messages, so a missing or misspelled key fails the type check.
const de: MessageSchema = {
  app,
  colorRole,
  recurrence,
  roles,
  auth,
  event,
  availability,
  reminders,
  weekStack,
  agenda,
  series,
  activity,
  notifications,
  booking,
  palette,
  emailNotifications,
  unsubscribe,
  rsvp,
}

export default de
