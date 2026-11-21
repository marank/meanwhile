import type { Occurrence } from '@/api'
import { DAY_MS, addDays, dayKey, startOfDay } from './days'

/** Which part of an occurrence a day shows: all of it, or its first, a middle or its last day. */
type AgendaSpan = 'single' | 'first' | 'middle' | 'last'

export interface AgendaEntry {
  occurrence: Occurrence
  span: AgendaSpan
  /** The day of the span (1-based) and the number of days, for events over several days. */
  dayIndex: number
  dayCount: number
}

export interface AgendaDay {
  /** Local midnight of the day. */
  date: Date
  key: string
  entries: AgendaEntry[]
}

/** All-day occurrences come as UTC midnights: of their first day, and of the day after their last. */
function utcDay(value: string): Date {
  const date = new Date(value)
  return new Date(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate())
}

/** The first and the last local day an occurrence touches. A timed event ending at midnight ends the day before. */
function occurrenceDays(occ: Occurrence): [Date, Date] {
  if (occ.all_day) {
    const first = utcDay(occ.start)
    const last = addDays(utcDay(occ.end), -1)
    return [first, last < first ? first : last]
  }
  const start = new Date(occ.start)
  const end = new Date(occ.end)
  const first = startOfDay(start)
  const last = end > start ? startOfDay(new Date(end.getTime() - 1)) : first
  return [first, last]
}

function sortKey(entry: AgendaEntry): [number, number, string] {
  const occ = entry.occurrence
  // All-day events and the middle days of longer ones come first, then by the time they start that day.
  const allDay = occ.all_day || entry.span === 'middle' || entry.span === 'last' ? 0 : 1
  const start = entry.span === 'single' || entry.span === 'first' ? new Date(occ.start).getTime() : 0
  return [allDay, start, occ.title.toLocaleLowerCase()]
}

function compareEntries(a: AgendaEntry, b: AgendaEntry): number {
  const [aAllDay, aStart, aTitle] = sortKey(a)
  const [bAllDay, bStart, bTitle] = sortKey(b)
  return aAllDay - bAllDay || aStart - bStart || aTitle.localeCompare(bTitle)
}

function spanOf(index: number, dayCount: number): AgendaSpan {
  if (dayCount === 1) return 'single'
  if (index === 0) return 'first'
  return index === dayCount - 1 ? 'last' : 'middle'
}

/** Lists an occurrence on each of its days from `firstDay` (inclusive) to `rangeEnd` (exclusive). */
function addToDays(days: Map<string, AgendaDay>, occurrence: Occurrence, firstDay: Date, rangeEnd: Date) {
  const [first, last] = occurrenceDays(occurrence)
  const dayCount = Math.round((last.getTime() - first.getTime()) / DAY_MS) + 1
  for (let index = 0; index < dayCount; index++) {
    const date = addDays(first, index)
    if (date < firstDay) continue
    if (date >= rangeEnd) break
    const key = dayKey(date)
    const day = days.get(key) ?? { date, key, entries: [] }
    days.set(key, day)
    day.entries.push({ occurrence, span: spanOf(index, dayCount), dayIndex: index + 1, dayCount })
  }
}

/**
 * The days from `rangeStart` (inclusive) to `rangeEnd` (exclusive) that have occurrences, in order. An event
 * over several days is listed on each of its days within the range.
 */
export function groupByDay(occurrences: Occurrence[], rangeStart: Date, rangeEnd: Date): AgendaDay[] {
  const days = new Map<string, AgendaDay>()
  const firstDay = startOfDay(rangeStart)
  for (const occurrence of occurrences) addToDays(days, occurrence, firstDay, rangeEnd)
  const sorted = [...days.values()].sort((a, b) => a.date.getTime() - b.date.getTime())
  for (const day of sorted) day.entries.sort(compareEntries)
  return sorted
}

/** Whether an occurrence matches every word of a search, in its title, place, resource, category or description. */
export function matchesSearch(occ: Occurrence, query: string): boolean {
  const words = query.toLocaleLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return true
  const text = [occ.title, occ.location, occ.resource_name, occ.category_name, occ.description]
    .filter(Boolean)
    .join('\n')
    .toLocaleLowerCase()
  return words.every((word) => text.includes(word))
}

/** Whether an occurrence is over by `now`. */
export function isPast(occ: Occurrence, now: Date): boolean {
  if (occ.all_day) return addDays(occurrenceDays(occ)[1], 1) <= now
  return new Date(occ.end) <= now
}
