/**
 * What the calendar shows, as it appears in the URL (`/calendar/<id>?...`):
 *
 *  - `view=month`, `view=week` or `view=list` (the events of a month as a list)
 *  - `date=2026-10-15`: the month (or week) of that day; `date=2026-10`: that month
 *  - `month=10`: that month of this year; `year=2025`: this month of that year; both: that month
 *  - `week=50`: that ISO week (Monday to Sunday) of this year, or of `year`; shown as a week unless `view=month`
 *
 * `date` wins over `week`, and `week` over `month`. Values that make no sense are ignored, so a mistyped link
 * still opens the calendar.
 */

export type CalendarViewName = 'month' | 'week' | 'list'

export interface CalendarTarget {
  view?: CalendarViewName
  /** A day within what is to be shown; the first of the month for `month`, `year` and `date=2026-10`. */
  date?: Date
}

type QueryValue = string | null | undefined | (string | null)[]

function single(value: QueryValue): string | undefined {
  const first = Array.isArray(value) ? value[0] : value
  return typeof first === 'string' ? first.trim() : undefined
}

function integer(value: string | undefined, digits: RegExp): number | undefined {
  return value !== undefined && digits.test(value) ? Number(value) : undefined
}

/** A real calendar day (not 30 February), in local time. */
function day(year: number, month: number, dayOfMonth: number): Date | undefined {
  const date = new Date(year, month - 1, dayOfMonth)
  const real = date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === dayOfMonth
  return real ? date : undefined
}

export function parseDate(value: string | undefined): Date | undefined {
  const match = value === undefined ? null : /^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?$/.exec(value)
  if (!match) return undefined
  return day(Number(match[1]), Number(match[2]), match[3] === undefined ? 1 : Number(match[3]))
}

/** The Monday of ISO week `week` of `year`, if the year has that week (some have 52, some 53). */
export function isoWeekStart(year: number, week: number): Date | undefined {
  const january4 = new Date(year, 0, 4)
  const start = new Date(year, 0, 4 - ((january4.getDay() + 6) % 7) + (week - 1) * 7)
  const thursday = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 3)
  return week >= 1 && thursday.getFullYear() === year ? start : undefined
}

export function parseCalendarQuery(query: Record<string, QueryValue>, today = new Date()): CalendarTarget {
  const target: CalendarTarget = {}
  const view = single(query.view)
  if (view === 'month' || view === 'week' || view === 'list') target.view = view

  const date = parseDate(single(query.date))
  if (date) {
    target.date = date
    return target
  }

  const month = integer(single(query.month), /^\d{1,2}$/)
  const year = integer(single(query.year), /^\d{4}$/)
  const week = integer(single(query.week), /^\d{1,2}$/)
  const weekStart = week === undefined ? undefined : isoWeekStart(year ?? isoYear(today), week)
  if (weekStart) {
    target.date = weekStart
    target.view ??= 'week'
    return target
  }
  const validMonth = month !== undefined && month >= 1 && month <= 12 ? month : undefined
  if (validMonth !== undefined || year !== undefined) {
    target.date = new Date(year ?? today.getFullYear(), (validMonth ?? today.getMonth() + 1) - 1, 1)
  }
  return target
}

/** The year the ISO week of a day belongs to (the first days of January can still be in the last week of the year before). */
function isoYear(date: Date): number {
  const thursday = new Date(date.getFullYear(), date.getMonth(), date.getDate() + 3 - ((date.getDay() + 6) % 7))
  return thursday.getFullYear()
}

/** Whether what is shown already is what the target asks for. */
export function showsTarget(target: CalendarTarget, view: CalendarViewName, rangeStart: Date, rangeEnd: Date): boolean {
  if (target.view && target.view !== view) return false
  return !target.date || (target.date >= rangeStart && target.date < rangeEnd)
}
