export interface Weekday {
  /** Day number as used by JavaScript dates and the API (0 = Sunday). */
  value: number
  /** i18n key below `event.` */
  key: string
  /** RFC 5545 weekday code */
  code: string
}

export const weekdays: Weekday[] = [
  { value: 0, key: 'sunday', code: 'SU' },
  { value: 1, key: 'monday', code: 'MO' },
  { value: 2, key: 'tuesday', code: 'TU' },
  { value: 3, key: 'wednesday', code: 'WE' },
  { value: 4, key: 'thursday', code: 'TH' },
  { value: 5, key: 'friday', code: 'FR' },
  { value: 6, key: 'saturday', code: 'SA' },
]

/** All weekdays, starting with `firstWeekday`. */
export function weekdaysFrom(firstWeekday: number): Weekday[] {
  return [...weekdays.slice(firstWeekday), ...weekdays.slice(0, firstWeekday)]
}
