/** Days as the calendar counts them: local dates, from midnight to midnight. */

export const DAY_MS = 24 * 60 * 60 * 1000

/** Local midnight of the day. */
export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

/** Local midnight of the day `days` later (or earlier); a DST change doesn't shift it. */
export function addDays(date: Date, days: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days)
}

/** The local date as YYYY-MM-DD, e.g. to group or compare by day. */
export function dayKey(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}
