// Recurrence rules (RFC 5545 RRULE) in the subset the editor can show. Expanding them into dates is
// left to the server (python-dateutil).

import { sortWithLastAtEnd } from './numberList'
import { weekdays } from './weekdays'

export type RecurrenceFrequency = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY'
export type RecurrenceEnd = 'never' | 'until' | 'count'
export type RecurrenceDayMode = 'date' | 'weekday'

export interface RecurrenceRule {
  frequency: RecurrenceFrequency
  interval: number
  /** WEEKLY: weekday codes (MO…SU) */
  weekdays: string[]
  /** MONTHLY and YEARLY: on dates of the month, or on weekdays by position ("1st and 3rd Tuesday") */
  dayMode: RecurrenceDayMode
  /** Days of the month, 1–31; -1 is the last day */
  monthDays: number[]
  /** Positions of the weekday in the month, 1–5; -1 is the last */
  ordinals: number[]
  ordinalWeekday: string
  /** YEARLY: months, 1–12 */
  months: number[]
  end: RecurrenceEnd
  /** YYYY-MM-DD */
  until: string
  count: number
}

/** What the start date suggests for a new rule. */
export interface RecurrenceDefaults {
  weekday: string
  monthDay: number
  month: number
  ordinal: number
}

const WEEK_ORDER = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
const FREQUENCIES: RecurrenceFrequency[] = ['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']

export function recurrenceDefaults(start: Date): RecurrenceDefaults {
  const monthDay = start.getDate()
  return {
    weekday: weekdays[start.getDay()]!.code,
    monthDay,
    month: start.getMonth() + 1,
    // Days after the 28th are named from the end of the month: "last Friday".
    ordinal: monthDay > 28 ? -1 : Math.ceil(monthDay / 7),
  }
}

export function defaultRecurrenceRule(defaults: RecurrenceDefaults): RecurrenceRule {
  return {
    frequency: 'WEEKLY',
    interval: 1,
    weekdays: [defaults.weekday],
    dayMode: 'date',
    monthDays: [defaults.monthDay],
    ordinals: [defaults.ordinal],
    ordinalWeekday: defaults.weekday,
    months: [defaults.month],
    end: 'never',
    until: '',
    count: 10,
  }
}

function numberList(value: string | undefined, valid: (n: number) => boolean): number[] | null {
  if (value === undefined) return []
  const numbers = value.split(',').map(Number)
  return numbers.every((n) => Number.isInteger(n) && valid(n)) ? numbers : null
}

/**
 * Reads a rule into the editor's model. Returns null for an empty rule and for rules the editor can't
 * represent (e.g. BYSETPOS or several ordinal weekdays from other clients); those are kept as they are.
 */
export function parseRrule(value: string | null, defaults: RecurrenceDefaults): RecurrenceRule | null {
  if (!value) return null
  const parts: Record<string, string> = {}
  for (const part of value.replace(/^RRULE:/, '').split(';')) {
    const [key, partValue] = part.split('=', 2)
    if (!key || partValue === undefined) return null
    parts[key] = partValue
  }
  const known = new Set(['FREQ', 'INTERVAL', 'UNTIL', 'COUNT', 'BYDAY', 'BYMONTHDAY', 'BYMONTH', 'WKST'])
  if (Object.keys(parts).some((key) => !known.has(key)) || (parts.WKST && parts.WKST !== 'MO')) return null

  const frequency = parts.FREQ as RecurrenceFrequency
  if (!FREQUENCIES.includes(frequency)) return null
  const rule = defaultRecurrenceRule(defaults)
  rule.frequency = frequency
  rule.interval = Math.max(1, Number(parts.INTERVAL) || 1)

  const monthDays = numberList(parts.BYMONTHDAY, (n) => (n >= 1 && n <= 31) || n === -1)
  const months = numberList(parts.BYMONTH, (n) => n >= 1 && n <= 12)
  if (!monthDays || !months) return null

  if (frequency === 'DAILY') {
    if (parts.BYDAY || monthDays.length || months.length) return null
  } else if (frequency === 'WEEKLY') {
    const days = parts.BYDAY?.split(',') ?? [defaults.weekday]
    if (!days.every((day) => WEEK_ORDER.includes(day)) || monthDays.length || months.length) return null
    rule.weekdays = days
  } else {
    if (frequency === 'MONTHLY' && months.length) return null
    if (months.length) rule.months = months
    if (parts.BYDAY) {
      // Several positions of one weekday ("1TU,3TU"); mixed weekdays are beyond the editor.
      const entries = parts.BYDAY.split(',').map((entry) => entry.match(/^([1-5]|-1)(MO|TU|WE|TH|FR|SA|SU)$/))
      const weekday = entries[0]?.[2]
      if (monthDays.length || !entries.every((entry) => entry && entry[2] === weekday)) return null
      rule.dayMode = 'weekday'
      rule.ordinals = sortWithLastAtEnd(entries.map((entry) => Number(entry![1])))
      rule.ordinalWeekday = weekday!
    } else if (monthDays.length) {
      rule.monthDays = monthDays
    }
  }

  if (parts.UNTIL) {
    if (!/^\d{8}/.test(parts.UNTIL)) return null
    rule.end = 'until'
    rule.until = `${parts.UNTIL.slice(0, 4)}-${parts.UNTIL.slice(4, 6)}-${parts.UNTIL.slice(6, 8)}`
  } else if (parts.COUNT) {
    rule.end = 'count'
    rule.count = Math.max(1, Number(parts.COUNT) || 1)
  }
  return rule
}

/** The rule's pattern without its end, e.g. to compare it with the presets. */
function patternParts(rule: RecurrenceRule): string[] {
  const parts = [`FREQ=${rule.frequency}`]
  const interval = Math.floor(rule.interval) || 1
  if (interval > 1) parts.push(`INTERVAL=${interval}`)
  if (rule.frequency === 'WEEKLY') {
    const days = WEEK_ORDER.filter((day) => rule.weekdays.includes(day))
    if (days.length) parts.push(`BYDAY=${days.join(',')}`)
  }
  if (rule.frequency === 'YEARLY') parts.push(`BYMONTH=${[...new Set(rule.months)].sort((a, b) => a - b).join(',')}`)
  if (rule.frequency === 'MONTHLY' || rule.frequency === 'YEARLY') {
    parts.push(
      rule.dayMode === 'date'
        ? `BYMONTHDAY=${sortWithLastAtEnd(rule.monthDays).join(',')}`
        : `BYDAY=${sortWithLastAtEnd(rule.ordinals)
            .map((ordinal) => `${ordinal}${rule.ordinalWeekday}`)
            .join(',')}`,
    )
  }
  return parts
}

export function buildRrule(rule: RecurrenceRule | null): string | null {
  if (!rule) return null
  const parts = patternParts(rule)
  // A date-only UNTIL, which the server reads as through that day in the event's zone.
  if (rule.end === 'until' && rule.until) parts.push(`UNTIL=${rule.until.replaceAll('-', '')}`)
  else if (rule.end === 'count') parts.push(`COUNT=${Math.max(1, Math.floor(rule.count) || 1)}`)
  return parts.join(';')
}

// Presets

export const recurrencePresets = [
  'daily',
  'weekdays',
  'weekly',
  'biweekly',
  'monthlyDate',
  'monthlyWeekday',
  'yearly',
] as const
export type RecurrencePreset = (typeof recurrencePresets)[number]

/** The pattern of a preset for the given start date; its end is left to the caller. */
export function presetRule(preset: RecurrencePreset, defaults: RecurrenceDefaults): RecurrenceRule {
  const rule = defaultRecurrenceRule(defaults)
  switch (preset) {
    case 'daily':
      return { ...rule, frequency: 'DAILY' }
    case 'weekdays':
      return { ...rule, weekdays: ['MO', 'TU', 'WE', 'TH', 'FR'] }
    case 'weekly':
      return rule
    case 'biweekly':
      return { ...rule, interval: 2 }
    case 'monthlyDate':
      return { ...rule, frequency: 'MONTHLY' }
    case 'monthlyWeekday':
      return { ...rule, frequency: 'MONTHLY', dayMode: 'weekday' }
    case 'yearly':
      return { ...rule, frequency: 'YEARLY' }
  }
}

/** The preset whose pattern the rule has, ignoring how it ends. */
export function matchingPreset(rule: RecurrenceRule, defaults: RecurrenceDefaults): RecurrencePreset | null {
  const pattern = patternParts(rule).join(';')
  return recurrencePresets.find((preset) => patternParts(presetRule(preset, defaults)).join(';') === pattern) ?? null
}
