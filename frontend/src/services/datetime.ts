import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { WEEK_ORDER } from './weekdays'

function toDate(value: string | Date): Date {
  return value instanceof Date ? value : new Date(value)
}

/** The browser's IANA time zone, e.g. "Europe/Berlin". */
export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

// Creating an Intl.DateTimeFormat is expensive; lists format many dates with the same few settings.
const formatters = new Map<string, Intl.DateTimeFormat>()

function formatter(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const locale = i18n.global.locale.value
  const key = `${locale}|${JSON.stringify(options)}`
  let cached = formatters.get(key)
  if (!cached) {
    cached = new Intl.DateTimeFormat(locale, options)
    formatters.set(key, cached)
  }
  return cached
}

export function hour12(): boolean | undefined {
  const pref = useAuthStore().user?.time_format ?? 'auto'
  if (pref === '12h') return true
  if (pref === '24h') return false
  return undefined
}

export function formatDate(value: string | Date): string {
  const date = toDate(value)
  const pref = useAuthStore().user?.date_format ?? 'auto'
  const day = pad(date.getDate())
  const month = pad(date.getMonth() + 1)
  const year = String(date.getFullYear())
  if (pref === 'dmy') return `${day}.${month}.${year}`
  if (pref === 'mdy') return `${month}/${day}/${year}`
  if (pref === 'ymd') return `${year}-${month}-${day}`
  return formatter({ year: 'numeric', month: 'numeric', day: 'numeric' }).format(date)
}

/** The day an all-day value names (midnight UTC, or a bare date), the same in every time zone. */
export function formatCalendarDate(value: string): string {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return formatDate(new Date(year!, month! - 1, day))
}

export function formatTime(value: string | Date): string {
  return formatter({ hour: 'numeric', minute: '2-digit', hour12: hour12() }).format(toDate(value))
}

export function formatDateTime(value: string | Date): string {
  const date = toDate(value)
  return `${formatDate(date)} ${formatTime(date)}`
}

/** Localized name of a weekday given as RFC 5545 code (MO…SU). */
export function weekdayName(code: string, style: 'long' | 'short' = 'long'): string {
  // 1 January 2024 was a Monday.
  return formatter({ weekday: style }).format(new Date(2024, 0, 1 + WEEK_ORDER.indexOf(code)))
}

/** Localized name of a month, 1–12. */
export function monthName(month: number, style: 'long' | 'short' = 'long'): string {
  return formatter({ month: style }).format(new Date(2024, month - 1, 1))
}

/** A day written out, e.g. "Montag, 5. Januar 2026" or "Monday, January 5, 2026". */
export function formatLongDate(date: Date): string {
  return formatter({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(date)
}

/** Day and month, e.g. "7. Oktober" or "October 7". */
export function formatDayMonth(date: Date): string {
  return formatter({ day: 'numeric', month: 'long' }).format(date)
}

/** Local calendar date as YYYY-MM-DD, the value format of `<input type="date">`. */
export function toDateInputValue(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** Local time as HH:MM, the value format of `<input type="time">`. */
export function toTimeInputValue(date: Date): string {
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** The hour the day starts at for a user who hasn't chosen one (User.day_start). */
export const DEFAULT_DAY_START = 9
const LAST_START_HOUR = 23

/**
 * When a new event on `day` starts if only the day was picked (a click on it in the month view, the
 * agenda's "new event"): when the user's day starts (`dayStart`, an hour), or today at the next
 * full hour after that.
 */
export function newEventStart(day: Date, dayStart = DEFAULT_DAY_START, now = new Date()): Date {
  const start = new Date(day.getFullYear(), day.getMonth(), day.getDate(), dayStart)
  if (toDateInputValue(day) === toDateInputValue(now)) {
    start.setHours(Math.min(Math.max(dayStart, now.getHours() + 1), LAST_START_HOUR))
  }
  return start
}

/** Whole calendar days from `value` back to `now`, in local time: 0 today, 1 yesterday. */
export function daysAgo(value: string | Date, now = new Date()): number {
  const day = (date: Date) => Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())
  return Math.round((day(now) - day(toDate(value))) / 86_400_000)
}

/**
 * How long ago `value` was, short: "just now", "5 min. ago", "3 hr. ago", "yesterday", "4 days ago";
 * older than a week, the date.
 */
export function formatTimeAgo(value: string | Date, now = new Date()): string {
  const date = toDate(value)
  const minutes = Math.floor((now.getTime() - date.getTime()) / 60_000)
  if (minutes < 1) return i18n.global.t('app.justNow')
  const relative = new Intl.RelativeTimeFormat(i18n.global.locale.value, { numeric: 'auto', style: 'short' })
  if (minutes < 60) return relative.format(-minutes, 'minute')
  const days = daysAgo(date, now)
  if (days === 0) return relative.format(-Math.floor(minutes / 60), 'hour')
  if (days < 7) return relative.format(-days, 'day')
  return formatDate(date)
}
