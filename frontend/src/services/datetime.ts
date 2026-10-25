import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'

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

const WEEK_ORDER = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']

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
