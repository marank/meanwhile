import type { DueReminder } from '@/api'
import { i18n } from '@/i18n'
import { formatDate, formatDateTime } from './datetime'

const DAY = 24 * 60
/** The longest time before an event a reminder may be (as the server accepts it). */
export const MAX_MINUTES_BEFORE = 4 * 7 * DAY

export type ReminderUnit = 'minutes' | 'hours' | 'days' | 'weeks'

export const UNIT_MINUTES: Record<ReminderUnit, number> = { minutes: 1, hours: 60, days: DAY, weeks: 7 * DAY }

/** A reminder as the editor shows it: an amount of a unit before a timed event … */
export interface TimedReminder {
  amount: number
  unit: ReminderUnit
}

/** … or a number of days before an all-day event, at a time of day ("HH:MM"). */
export interface AllDayReminder {
  days: number
  time: string
}

/** The largest unit that expresses the minutes exactly. */
export function toTimedReminder(minutes: number): TimedReminder {
  for (const unit of ['weeks', 'days', 'hours'] as const) {
    if (minutes > 0 && minutes % UNIT_MINUTES[unit] === 0) return { amount: minutes / UNIT_MINUTES[unit], unit }
  }
  return { amount: minutes, unit: 'minutes' }
}

export function fromTimedReminder({ amount, unit }: TimedReminder): number {
  return Math.round(amount * UNIT_MINUTES[unit])
}

/** All-day events start at midnight: 900 minutes before is the day before at 09:00. */
export function toAllDayReminder(minutes: number): AllDayReminder {
  const days = Math.ceil(minutes / DAY)
  const after = days * DAY - minutes
  return { days, time: `${pad(Math.floor(after / 60))}:${pad(after % 60)}` }
}

export function fromAllDayReminder({ days, time }: AllDayReminder): number {
  const [hours = 0, mins = 0] = time.split(':').map(Number)
  return days * DAY - (hours * 60 + mins)
}

/** Whether the minutes can be a reminder: not after the start and not too long before. */
export function isValidReminder(minutes: number): boolean {
  return Number.isInteger(minutes) && minutes >= 0 && minutes <= MAX_MINUTES_BEFORE
}

/** Reminder choices in minutes before the start; all-day events are reminded of at a time of day. */
export function reminderChoices(allDay: boolean): number[] {
  // All-day: on the day at midnight, the day before at 9:00, two days before at 9:00, a week before at 9:00.
  return allDay
    ? [0, DAY - 9 * 60, 2 * DAY - 9 * 60, 7 * DAY - 9 * 60]
    : [0, 5, 10, 15, 30, 60, 120, DAY, 2 * DAY, 7 * DAY]
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

export function reminderLabel(minutes: number, allDay: boolean): string {
  const { t } = i18n.global
  if (allDay) {
    if (minutes === 0) return t('reminders.onTheDay')
    // e.g. 900 minutes before midnight: the day before at 09:00.
    const { days, time } = toAllDayReminder(minutes)
    return days === 1 ? t('reminders.dayBeforeAt', { time }) : t('reminders.daysBeforeAt', { n: days, time })
  }
  if (minutes === 0) return t('reminders.atStart')
  if (minutes % (7 * DAY) === 0) return t('reminders.weeksBefore', minutes / (7 * DAY))
  if (minutes % DAY === 0) return t('reminders.daysBefore', minutes / DAY)
  if (minutes % 60 === 0) return t('reminders.hoursBefore', minutes / 60)
  return t('reminders.minutesBefore', minutes)
}

/** What a reminder says, e.g. in a toast: the title and when it starts. */
export function reminderText(title: string, start: string, allDay: boolean): string {
  const when = allDay ? formatDate(start) : formatDateTime(start)
  return i18n.global.t('reminders.due', { title: title || i18n.global.t('reminders.untitled'), when })
}

export function dueReminderText(reminder: DueReminder): string {
  return reminderText(reminder.title, reminder.start, reminder.all_day)
}
