import { beforeEach, describe, expect, it } from 'vitest'
import { i18n } from '@/i18n'
import {
  fromAllDayReminder,
  fromTimedReminder,
  isValidReminder,
  reminderChoices,
  reminderLabel,
  toAllDayReminder,
  toTimedReminder,
} from '../reminders'

describe('reminders', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'de'
  })

  it('names times before timed events in the largest whole unit', () => {
    expect(reminderLabel(0, false)).toBe('Zu Beginn')
    expect(reminderLabel(1, false)).toBe('1 Minute vorher')
    expect(reminderLabel(90, false)).toBe('90 Minuten vorher')
    expect(reminderLabel(120, false)).toBe('2 Stunden vorher')
    expect(reminderLabel(1440, false)).toBe('1 Tag vorher')
    expect(reminderLabel(10080, false)).toBe('1 Woche vorher')
  })

  it('names times before all-day events as a day and a time of day', () => {
    expect(reminderLabel(0, true)).toBe('Am Tag um 00:00')
    expect(reminderLabel(15 * 60, true)).toBe('Am Vortag um 09:00')
    expect(reminderLabel(2 * 1440 - 9 * 60, true)).toBe('2 Tage vorher um 09:00')
  })

  it('offers each choice once and only times before the start', () => {
    for (const allDay of [false, true]) {
      const choices = reminderChoices(allDay)
      expect(new Set(choices).size).toBe(choices.length)
      expect(choices.every((m) => m >= 0)).toBe(true)
    }
  })

  it('shows minutes in the largest whole unit and back', () => {
    expect(toTimedReminder(0)).toEqual({ amount: 0, unit: 'minutes' })
    expect(toTimedReminder(90)).toEqual({ amount: 90, unit: 'minutes' })
    expect(toTimedReminder(120)).toEqual({ amount: 2, unit: 'hours' })
    expect(toTimedReminder(2880)).toEqual({ amount: 2, unit: 'days' })
    expect(toTimedReminder(20160)).toEqual({ amount: 2, unit: 'weeks' })
    for (const minutes of [0, 5, 90, 120, 2880, 20160])
      expect(fromTimedReminder(toTimedReminder(minutes))).toBe(minutes)
  })

  it('shows all-day reminders as days before at a time of day and back', () => {
    expect(toAllDayReminder(900)).toEqual({ days: 1, time: '09:00' })
    expect(toAllDayReminder(0)).toEqual({ days: 0, time: '00:00' })
    expect(fromAllDayReminder({ days: 2, time: '18:30' })).toBe(2 * 1440 - (18 * 60 + 30))
    // On the day itself after midnight would be after the start.
    expect(isValidReminder(fromAllDayReminder({ days: 0, time: '09:00' }))).toBe(false)
  })

  it('accepts reminders between the start and four weeks before', () => {
    expect(isValidReminder(0)).toBe(true)
    expect(isValidReminder(4 * 7 * 1440)).toBe(true)
    expect(isValidReminder(4 * 7 * 1440 + 1)).toBe(false)
    expect(isValidReminder(Number.NaN)).toBe(false)
  })
})
