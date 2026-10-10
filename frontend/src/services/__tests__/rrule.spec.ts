import { describe, expect, it } from 'vitest'
import {
  buildRrule,
  defaultRecurrenceRule,
  matchingPreset,
  parseRrule,
  presetRule,
  recurrenceDefaults,
  recurrencePresets,
} from '../rrule'

const day = (value: string) => new Date(`${value}T00:00:00`)
// A Wednesday, the 7th: the first Wednesday of October.
const defaults = recurrenceDefaults(day('2026-10-07'))

describe('recurrenceDefaults', () => {
  it('reads weekday, date and ordinal from the start date', () => {
    expect(defaults).toEqual({ weekday: 'WE', monthDay: 7, month: 10, ordinal: 1 })
  })

  it('names days after the 28th from the end of the month', () => {
    expect(recurrenceDefaults(day('2026-10-30')).ordinal).toBe(-1)
  })
})

describe('parseRrule', () => {
  it('returns null for an empty rule', () => {
    expect(parseRrule('', defaults)).toBeNull()
  })

  it('reads weekly rules', () => {
    expect(parseRrule('RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE;COUNT=5', defaults)).toMatchObject({
      frequency: 'WEEKLY',
      interval: 2,
      weekdays: ['MO', 'WE'],
      end: 'count',
      count: 5,
    })
  })

  it('fills in what a plain rule leaves to the start date', () => {
    expect(parseRrule('FREQ=YEARLY', defaults)).toMatchObject({ months: [10], dayMode: 'date', monthDays: [7] })
    expect(parseRrule('FREQ=WEEKLY', defaults)).toMatchObject({ weekdays: ['WE'] })
  })

  it('reads several days of the month, including the last one', () => {
    expect(parseRrule('FREQ=MONTHLY;BYMONTHDAY=1,15,-1', defaults)).toMatchObject({ monthDays: [1, 15, -1] })
  })

  it('reads yearly rules on an ordinal weekday', () => {
    expect(parseRrule('FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU', defaults)).toMatchObject({
      months: [3],
      dayMode: 'weekday',
      ordinals: [-1],
      ordinalWeekday: 'SU',
    })
  })

  it('reads several positions of one weekday', () => {
    expect(parseRrule('FREQ=MONTHLY;BYDAY=3TU,1TU,-1TU', defaults)).toMatchObject({
      dayMode: 'weekday',
      ordinals: [1, 3, -1],
      ordinalWeekday: 'TU',
    })
  })

  it('reads the end date of an UNTIL rule', () => {
    expect(parseRrule('FREQ=DAILY;UNTIL=20261231T235959Z', defaults)).toMatchObject({
      end: 'until',
      until: '2026-12-31',
    })
  })

  it.each([
    'FREQ=MONTHLY;BYDAY=MO,TU;BYSETPOS=1',
    'FREQ=MONTHLY;BYDAY=1MO,3TU',
    'FREQ=HOURLY',
    'FREQ=WEEKLY;BYMONTH=3',
    'FREQ=MONTHLY;BYMONTHDAY=-2',
  ])('leaves rules the editor cannot show alone: %s', (rule) => {
    expect(parseRrule(rule, defaults)).toBeNull()
  })
})

describe('buildRrule', () => {
  it('returns null without a rule', () => {
    expect(buildRrule(null)).toBeNull()
  })

  it('writes days of the month in order, the last day at the end', () => {
    const rule = { ...defaultRecurrenceRule(defaults), frequency: 'MONTHLY' as const, monthDays: [-1, 15, 1] }
    expect(buildRrule(rule)).toBe('FREQ=MONTHLY;BYMONTHDAY=1,15,-1')
  })

  it.each([
    'FREQ=DAILY;INTERVAL=3;COUNT=4',
    'FREQ=WEEKLY;BYDAY=MO,TH;UNTIL=20270101T235959Z',
    'FREQ=MONTHLY;BYDAY=2TU',
    'FREQ=MONTHLY;BYDAY=1TU,3TU,-1TU',
    'FREQ=MONTHLY;BYDAY=5FR',
    'FREQ=MONTHLY;BYMONTHDAY=1,15,-1',
    'FREQ=YEARLY;BYMONTH=1,4,7,10;BYMONTHDAY=1',
    'FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU',
  ])('round-trips %s', (rule) => {
    expect(buildRrule(parseRrule(rule, defaults))).toBe(rule)
  })
})

describe('presets', () => {
  it('are recognized again from their own pattern, whatever the end', () => {
    for (const preset of recurrencePresets) {
      const rule = { ...presetRule(preset, defaults), end: 'count' as const, count: 3 }
      expect(matchingPreset(rule, defaults)).toBe(preset)
    }
  })

  it('treat anything else as custom', () => {
    expect(matchingPreset({ ...presetRule('weekly', defaults), interval: 3 }, defaults)).toBeNull()
  })
})
