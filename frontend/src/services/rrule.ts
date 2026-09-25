export type RecurrenceFrequency = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY'
export type RecurrenceEnd = 'never' | 'until' | 'count'
export type RecurrenceMonthMode = 'date' | 'weekday'

export interface RecurrenceRule {
  frequency: RecurrenceFrequency
  interval: number
  weekdays: string[]
  monthMode: RecurrenceMonthMode
  monthDay: number
  monthOrdinal: string
  monthWeekday: string
  end: RecurrenceEnd
  until: string
  count: number
  extraParts: string[]
  preserveAdvancedMonthlyRule: boolean
}

export function parseRrule(value: string, defaultMonthDay: number): RecurrenceRule | null {
  if (!value) return null
  const parts = Object.fromEntries(
    value.replace(/^RRULE:/, '').split(';').map((part) => part.split('=', 2)),
  )
  const frequency = (parts.FREQ || 'WEEKLY') as RecurrenceFrequency
  const monthDay = Number(parts.BYMONTHDAY)
  const hasSimpleMonthDay = Number.isInteger(monthDay) && monthDay >= 1 && monthDay <= 31
  const ordinalWeekday = frequency === 'MONTHLY'
    ? parts.BYDAY?.match(/^([1-4]|-1)(MO|TU|WE|TH|FR|SA|SU)$/)
    : null
  const preserveAdvancedMonthlyRule = frequency === 'MONTHLY'
    && Boolean((parts.BYDAY && !ordinalWeekday) || (parts.BYMONTHDAY && !hasSimpleMonthDay))
  const handled = new Set(['FREQ', 'INTERVAL', 'UNTIL', 'COUNT'])
  if (!preserveAdvancedMonthlyRule) handled.add('BYDAY')
  if (hasSimpleMonthDay) handled.add('BYMONTHDAY')

  let end: RecurrenceEnd = 'never'
  let until = ''
  let count = 10
  if (parts.UNTIL) {
    end = 'until'
    until = `${parts.UNTIL.slice(0, 4)}-${parts.UNTIL.slice(4, 6)}-${parts.UNTIL.slice(6, 8)}`
  } else if (parts.COUNT) {
    end = 'count'
    count = Math.max(1, Number(parts.COUNT) || 1)
  }

  return {
    frequency,
    interval: Math.max(1, Number(parts.INTERVAL) || 1),
    weekdays: frequency === 'WEEKLY' ? parts.BYDAY?.split(',').filter(Boolean) || [] : [],
    monthMode: ordinalWeekday ? 'weekday' : 'date',
    monthDay: hasSimpleMonthDay ? monthDay : defaultMonthDay,
    monthOrdinal: ordinalWeekday?.[1] || '1',
    monthWeekday: ordinalWeekday?.[2] || 'MO',
    end,
    until,
    count,
    preserveAdvancedMonthlyRule,
    extraParts: value
      .replace(/^RRULE:/, '')
      .split(';')
      .filter((part) => !handled.has(part.split('=', 1)[0]!)),
  }
}

export function buildRrule(rule: RecurrenceRule | null): string | null {
  if (!rule) return null
  const parts = [`FREQ=${rule.frequency}`]
  if (rule.interval > 1) parts.push(`INTERVAL=${rule.interval}`)
  if (rule.frequency === 'WEEKLY' && rule.weekdays.length) {
    parts.push(`BYDAY=${rule.weekdays.join(',')}`)
  }
  if (rule.frequency === 'MONTHLY' && !rule.preserveAdvancedMonthlyRule) {
    if (rule.monthMode === 'date') {
      parts.push(`BYMONTHDAY=${Math.max(1, Math.min(31, rule.monthDay))}`)
    } else {
      parts.push(`BYDAY=${rule.monthOrdinal}${rule.monthWeekday}`)
    }
  }
  if (rule.end === 'until' && rule.until) {
    parts.push(`UNTIL=${rule.until.replaceAll('-', '')}T235959Z`)
  } else if (rule.end === 'count') {
    parts.push(`COUNT=${Math.max(1, rule.count)}`)
  }
  parts.push(...rule.extraParts)
  return parts.join(';')
}
